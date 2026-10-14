# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Replay production scene copies and display selection with delayed frame consumers.

This checks recorded Vulkan operations and their ownership, not NVIDIA's GPU
algorithm. Revision 30 is the control: retaining frame A did not preserve it.
"""
import argparse
import ast
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '89bb432c048d4bc40905b5507ec365568739e1ca'
COPY_PATH = 'gpu/shadps4/video_core/renderer_vulkan/vk_frame_generation.cpp'
UPSCALER_PATH = 'gpu/shadps4/video_core/renderer_vulkan/vk_temporal_upscaler.cpp'

EXTRA = r'''
#include <mutex>
#include <algorithm>
#include <cstdlib>
namespace BbSettings {
enum { FrameGenerationOff=0 };
struct Settings { const char* frame_generation_problem{}; } settings;
Settings& Get() { return settings; }
}
struct FakeInstance {
    vk::Device device;
    VmaAllocator allocator;
    vk::Device GetDevice() const { return device; }
    VmaAllocator GetAllocator() const { return allocator; }
};
struct FakeScheduler {
    std::vector<std::function<void()>> retired;
    template<class F> void DeferOperation(F keep) { retired.emplace_back(std::move(keep)); }
    void EndRendering() {}
    vk::CommandBuffer CommandBuffer() { return vk::CommandBuffer{Handle<VkCommandBuffer>()}; }
};
struct DumpImage { vk::Image image; unsigned w,h,bytes; const char* name; const char* format; };
void DumpImages(const FakeInstance&,FakeScheduler&,vk::CommandBuffer,int,std::initializer_list<DumpImage>) { assert(false); }
namespace Vulkan {
class TemporalUpscaler {
public:
    const FakeInstance& instance;
    FakeScheduler& scheduler;
    vk::Image motion_image;
    static constexpr size_t MaxFrozenScenes=8;
    std::vector<std::shared_ptr<FrameGenerationDepthCopy>> frozen_fg_inputs;
    FrameGenerationSource fg_source;
    struct Display { vk::Image image;vk::Format format;unsigned width,height;vk::ImageView view; };
    struct DisplayImage {
        vk::Image image;vk::Format format{};unsigned width{},height{};bool valid{};
        std::vector<int> views;
        FrameGenerationSource frame_source;
    };
    std::mutex display_mutex;
    std::unordered_map<VAddr,DisplayImage> displays;
    TemporalUpscaler(const FakeInstance& i,FakeScheduler& s,vk::Image motion)
        : instance{i},scheduler{s},motion_image{motion} {}
    vk::ImageView Mirror(vk::Image image,std::vector<int>&,vk::Format,vk::ComponentMapping) {
        return vk::ImageView(reinterpret_cast<VkImageView>(VkImage(image)));
    }
    std::shared_ptr<const FrameGenerationDepthCopy> FreezeFrameGenerationInputs(
        vk::CommandBuffer,vk::Image,vk::Format,unsigned,unsigned);
    void CompleteFrame(VAddr);
    bool DisplayOverride(VAddr,Display&,vk::Format,FrameGenerationSource&);
};
__UPSCALE_METHODS__
}
'''

MAIN = r'''
int main() {
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCreateImageView=View;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkDestroyImageView=DestroyView;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdPipelineBarrier2=Barrier;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdCopyImage=Copy;
    const vk::Device device{Handle<VkDevice>()};
    const auto allocator=Handle<VmaAllocator>();
    const vk::CommandBuffer command{Handle<VkCommandBuffer>()};
#if !CURRENT
    for(const auto format:{vk::Format::eD32Sfloat,vk::Format::eD32SfloatS8Uint,vk::Format::eR32Sfloat}) {
        const auto raw=Handle<VkImage>();
        images.emplace(raw,ImageData{VkFormat(format),8,8,std::vector<float>(64,.5f)});
        std::shared_ptr<Vulkan::FrameGenerationDepthCopy> copy;
        assert(Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,raw,format,8,8,copy));
        Execute();auto frame_a=std::shared_ptr<const Vulkan::FrameGenerationDepthCopy>(copy);
        images.at(raw).depth.assign(64,.7f);
        assert(Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,raw,format,8,8,copy));
        Execute();assert(images.at(VkImage(vk::Image(frame_a->depth))).depth.front()==.7f);
        assert(copy.get()==frame_a.get());
        copy.reset();frame_a.reset();images.erase(raw);
    }
    std::puts("PASS: unchanged Revision 30 reproduces frame B overwriting retained frame A depth (D32/D32S8/R32).");
#else
    unsigned cases=0;
    for(const auto format:{vk::Format::eD32Sfloat,vk::Format::eD32SfloatS8Uint,vk::Format::eR32Sfloat}) {
      for(const unsigned width:{8u,64u,192u}) {
       for(const auto color_format:{vk::Format::eR8G8B8A8Srgb,vk::Format::eA2B10G10R10UnormPack32}) {
        const unsigned height=8;
        const auto depth=Handle<VkImage>(),motion=Handle<VkImage>();
        const auto color_a_image=Handle<VkImage>(),color_b_image=Handle<VkImage>();
        images.emplace(depth,ImageData{VkFormat(format),width,height,std::vector<float>(width*height,.5f)});
        images.emplace(motion,ImageData{VK_FORMAT_R16G16_SFLOAT,width,height,std::vector<float>(width*height,4.f)});
        images.emplace(color_a_image,ImageData{VkFormat(color_format),width,height,std::vector<float>(width*height,.1f)});
        images.emplace(color_b_image,ImageData{VkFormat(color_format),width,height,std::vector<float>(width*height,.2f)});
        FakeInstance instance{device,allocator};FakeScheduler scheduler;
        {
            Vulkan::TemporalUpscaler upscaler(instance,scheduler,motion);
            const auto make_source=[&](float marker) {
                auto owner=upscaler.FreezeFrameGenerationInputs(command,depth,format,width,height);
                assert(owner);
                Vulkan::FrameGenerationSource source;
                source.depth_owner=owner;source.depth_view=*owner->view;
                source.motion_image=vk::Image(owner->motion);source.motion_view=*owner->motion_view;
                source.render_width=width;source.render_height=height;
                source.inverse_view[3]=marker;source.valid=true;
                return source;
            };
            upscaler.fg_source=make_source(1.f);upscaler.CompleteFrame(0x1000);
            auto& color_a=upscaler.displays.at(0x1000);
            color_a.valid=true;color_a.image=vk::Image(color_a_image);color_a.width=width;color_a.height=height;
            color_a.format=color_format;
            Execute();
            const auto source_a=upscaler.displays.at(0x1000).frame_source;
            assert(images.at(VkImage(source_a.motion_image)).depth.front()==4.f);
            // The next scene rewrites both scratch inputs before A's flip/SDK consumer.
            images.at(depth).depth.assign(width*height,.7f);
            images.at(motion).depth.assign(width*height,-8.f);
            upscaler.fg_source=make_source(2.f);upscaler.CompleteFrame(0x2000);
            auto& color_b=upscaler.displays.at(0x2000);
            color_b.image=vk::Image(color_b_image);color_b.width=width;color_b.height=height;color_b.format=color_format;
            Execute();
            Vulkan::TemporalUpscaler::Display display{};
            Vulkan::FrameGenerationSource selected{};
            assert(upscaler.DisplayOverride(0x1000,display,color_format,selected));
            assert(selected.inverse_view[3]==1.f && selected.depth_owner==source_a.depth_owner);
            assert(display.image==vk::Image(color_a_image) && display.format==color_format);
            assert(images.at(VkImage(display.image)).depth.front()==.1f);
            assert(images.at(VkImage(vk::Image(selected.depth_owner->depth))).depth.front()==.5f);
            assert(images.at(VkImage(selected.motion_image)).depth.front()==4.f);
            // Native AA has no redirected color, but still selects its own scene metadata.
            assert(!upscaler.DisplayOverride(0x2000,display,color_format,selected));
            assert(selected.inverse_view[3]==2.f);
            assert(images.at(VkImage(vk::Image(selected.depth_owner->depth))).depth.front()==.7f);
            assert(images.at(VkImage(selected.motion_image)).depth.front()==-8.f);
            auto native_b=selected;
            color_b.valid=true;
            assert(upscaler.DisplayOverride(0x2000,display,color_format,selected));
            assert(display.image==vk::Image(color_b_image) && !selected.valid && !selected.depth_owner);
            assert(images.at(VkImage(display.image)).depth.front()==.2f);
            assert(!upscaler.DisplayOverride(0x3000,display,color_format,selected));
            assert(!selected.valid && !selected.depth_owner);
            upscaler.CompleteFrame(0x2000); // a menu/failed scene must not reuse previous FG data
            assert(upscaler.DisplayOverride(0x2000,display,color_format,selected));
            assert(!selected.valid && !selected.depth_owner);
            // Even a discarded scene remains owned until its producer commands retire.
            while(upscaler.frozen_fg_inputs.size()<upscaler.MaxFrozenScenes) {
                auto ignored=make_source(3.f);
            }
            assert(!upscaler.FreezeFrameGenerationInputs(command,depth,format,width,height));
            Execute();
            const auto before=next_handle;
            scheduler.retired.clear();
            auto recycled=make_source(4.f);Execute();
            assert(next_handle==before && upscaler.frozen_fg_inputs.size()==8); // warmed free slot
            assert(images.at(VkImage(vk::Image(source_a.depth_owner->depth))).depth.front()==.5f);
            assert(images.at(VkImage(source_a.motion_image)).depth.front()==4.f);
            recycled.depth_owner.reset();
        }
        scheduler.retired.clear();
        images.erase(depth);images.erase(motion);images.erase(color_a_image);images.erase(color_b_image);++cases;
       }
      }
    }
    assert(images.empty() && views.empty() && commands.empty());
    std::printf("PASS: %u production scene-input cases: immutable depth/motion, delayed flips, per-buffer camera/color selection, SDR/HDR, native AA, invalid scenes, bounded pool and GPU-producer retirement.\n",cases);
#endif
}
'''


def read(path, revision=None):
    return subprocess.check_output(['git','show',revision+':'+path],cwd=ROOT,text=True) if revision else (ROOT/path).read_text()


def section(source,start,end):
    return source[source.index(start):source.index(end,source.index(start))]


def prepare(folder):
    folder.mkdir(parents=True,exist_ok=True)
    tree=ast.parse((ROOT/'tests/test_fg_depth_snapshot.py').read_text())
    harness=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=='HARNESS' for t in n.targets))
    harness=harness[:harness.index('int main()')]
    for name,ref in [('revision30',BASE),('current',None)]:
        methods=section(read(COPY_PATH,ref),'FrameGeneration::Image::~Image()','FrameGeneration::FrameGeneration(')
        program=harness.replace('__METHODS__',methods)
        if ref is None:
            source=read(UPSCALER_PATH)
            upscaler=(section(source,'std::shared_ptr<const FrameGenerationDepthCopy> TemporalUpscaler::FreezeFrameGenerationInputs(', 'bool TemporalUpscaler::OnFrameStart()')
                      + section(source,'bool TemporalUpscaler::DisplayOverride(', '} // namespace Vulkan'))
            extra=EXTRA.replace('__UPSCALE_METHODS__',upscaler)
            program=program[:program.index('void Execute()')]+extra+program[program.index('void Execute()'):]
        program='#define CURRENT '+('0' if ref else '1')+'\n'+program+MAIN
        (folder/(name+'.cpp')).write_text(program)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',type=Path)
    args=parser.parse_args()
    if args.prepare:prepare(args.prepare);return
    with tempfile.TemporaryDirectory(prefix='fg-frame-inputs-') as temp:
        folder=Path(temp);prepare(folder)
        for name in ['revision30','current']:
            binary=folder/name
            subprocess.run(['g++','-std=c++23','-O1','-UNDEBUG','-Igpu/shadps4',
                '-Iout/test-headers','-Iout/test-headers/vma',str(folder/(name+'.cpp')),'-o',str(binary)],cwd=ROOT,check=True)
            subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=30)


if __name__=='__main__':main()
