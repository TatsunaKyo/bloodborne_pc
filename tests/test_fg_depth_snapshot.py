# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production FG depth-copy methods with recorded Vulkan calls.

The command simulator reproduces UI clearing the borrowed scene depth before
presentation. This is a resource/recording check; it does not run NVIDIA FG.
"""
from pathlib import Path
import subprocess
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
source = (ROOT / 'gpu/shadps4/video_core/renderer_vulkan/vk_frame_generation.cpp').read_text()
methods = source[source.index('FrameGeneration::Image::~Image()'):source.index('FrameGeneration::FrameGeneration(')]
headers = ROOT / 'out/test-headers'
if not (headers/'vma/vk_mem_alloc.h').is_file():
    headers = WORK / 'windows-build/sysroot/clang64/include'

HARNESS = r'''
#include "video_core/renderer_vulkan/vk_frame_generation.h"
#include <vk_mem_alloc.h>
#include <cassert>
#include <cstdio>
#include <unordered_map>
#include <vector>
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
struct ImageData { VkFormat format; unsigned width,height; std::vector<float> depth; };
std::unordered_map<VkImage,ImageData> images;
std::unordered_map<VkImageView,VkImage> views;
std::vector<std::function<void()>> commands;
uintptr_t next_handle=10;
unsigned copies{},barriers{};
bool reject_allocation{};
template<class T> T Handle() { return reinterpret_cast<T>(++next_handle); }
VKAPI_ATTR VkResult VKAPI_CALL View(VkDevice,const VkImageViewCreateInfo* info,
                                    const VkAllocationCallbacks*,VkImageView* view) {
    assert(images.contains(info->image));
    const auto aspect=info->format==VK_FORMAT_R32_SFLOAT ? VK_IMAGE_ASPECT_COLOR_BIT : VK_IMAGE_ASPECT_DEPTH_BIT;
    assert(info->subresourceRange.aspectMask==aspect);
    *view=Handle<VkImageView>();views[*view]=info->image;return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL DestroyView(VkDevice,VkImageView view,const VkAllocationCallbacks*) {
    assert(views.erase(view)==1);
}
VKAPI_ATTR void VKAPI_CALL Barrier(VkCommandBuffer,const VkDependencyInfo* dependency) {
    ++barriers;
    for(unsigned i=0;i<dependency->imageMemoryBarrierCount;++i) {
        const auto& b=dependency->pImageMemoryBarriers[i];
        assert(images.contains(b.image));
        assert(b.newLayout==VK_IMAGE_LAYOUT_GENERAL);
        assert(b.srcQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED && b.dstQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED);
        const auto format=images.at(b.image).format;
        const auto expected=format==VK_FORMAT_R32_SFLOAT ? VK_IMAGE_ASPECT_COLOR_BIT :
            VK_IMAGE_ASPECT_DEPTH_BIT|(format==VK_FORMAT_D32_SFLOAT_S8_UINT ? VK_IMAGE_ASPECT_STENCIL_BIT : 0);
        assert(b.subresourceRange.aspectMask==unsigned(expected));
    }
}
VKAPI_ATTR void VKAPI_CALL Copy(VkCommandBuffer,VkImage source,VkImageLayout source_layout,
                                VkImage target,VkImageLayout target_layout,unsigned count,
                                const VkImageCopy* region) {
    assert(count==1 && source_layout==VK_IMAGE_LAYOUT_GENERAL && target_layout==VK_IMAGE_LAYOUT_GENERAL);
    assert(images.at(source).format==images.at(target).format);
    assert(region->extent.width==images.at(target).width && region->extent.height==images.at(target).height);
    const auto aspect=images.at(source).format==VK_FORMAT_R32_SFLOAT ? VK_IMAGE_ASPECT_COLOR_BIT : VK_IMAGE_ASPECT_DEPTH_BIT;
    assert(region->srcSubresource.aspectMask==unsigned(aspect) && region->dstSubresource.aspectMask==unsigned(aspect));
    ++copies;
    commands.push_back([source,target] {images.at(target).depth=images.at(source).depth;});
}
extern "C" VkResult vmaCreateImage(VmaAllocator,const VkImageCreateInfo* info,
                                   const VmaAllocationCreateInfo*,VkImage* image,
                                   VmaAllocation* allocation,VmaAllocationInfo*) {
    if(reject_allocation) return VK_ERROR_OUT_OF_DEVICE_MEMORY;
    assert(info->usage==(VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT));
    *image=Handle<VkImage>();*allocation=Handle<VmaAllocation>();
    images.emplace(*image,ImageData{info->format,info->extent.width,info->extent.height,
        std::vector<float>(info->extent.width*info->extent.height,-1)});
    return VK_SUCCESS;
}
extern "C" void vmaDestroyImage(VmaAllocator,VkImage image,VmaAllocation) {
    assert(images.erase(image)==1);
}
namespace Vulkan {
constexpr auto usage = vk::ImageUsageFlagBits::eSampled | vk::ImageUsageFlagBits::eStorage |
    vk::ImageUsageFlagBits::eTransferSrc | vk::ImageUsageFlagBits::eTransferDst;
__METHODS__
}
void Execute() {for(auto& command:commands)command();commands.clear();}
int main() {
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCreateImageView=View;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkDestroyImageView=DestroyView;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdPipelineBarrier2=Barrier;
    VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdCopyImage=Copy;
    const vk::Device device{Handle<VkDevice>()};
    const auto allocator=Handle<VmaAllocator>();const vk::CommandBuffer command{Handle<VkCommandBuffer>()};
    unsigned cases=0;
    for(const auto format:{vk::Format::eD32Sfloat,vk::Format::eD32SfloatS8Uint,vk::Format::eR32Sfloat}) {
        for(const unsigned width:{8u,64u,192u}) {
            const unsigned height=8;
            const auto source=Handle<VkImage>();
            images.emplace(source,ImageData{VkFormat(format),width,height,std::vector<float>(width*height,.5f)});
            std::shared_ptr<Vulkan::FrameGenerationDepthCopy> copy;
            assert(Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,source,format,width,height,copy));
            const auto saved=VkImage(vk::Image(copy->depth));
            // Queue the real failure trigger: later UI writes replace scene depth.
            commands.push_back([source] {std::fill(images.at(source).depth.begin(),images.at(source).depth.end(),0.f);});
            Execute();
            assert(images.at(source).depth.front()==0); // old borrowed view is now wrong
            assert(images.at(saved).depth.front()==.5f); // production copy preserves the scene
            auto owner=std::shared_ptr<const Vulkan::FrameGenerationDepthCopy>(copy);
            std::fill(images.at(source).depth.begin(),images.at(source).depth.end(),.7f);
            assert(Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,source,format,width,height,copy));
            assert(VkImage(vk::Image(copy->depth))==saved); // ordinary frames do not allocate or wait
            Execute();assert(images.at(saved).depth.front()==.7f);
            const auto larger=Handle<VkImage>();
            images.emplace(larger,ImageData{VkFormat(format),width*2,height,std::vector<float>(width*2*height,.6f)});
            assert(Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,larger,format,width*2,height,copy));
            Execute();assert(VkImage(vk::Image(copy->depth))!=saved && images.contains(saved));
            owner.reset();assert(!images.contains(saved)); // release after last frame owner
            assert(images.at(VkImage(vk::Image(copy->depth))).depth.front()==.6f);
            reject_allocation=true;
            std::shared_ptr<Vulkan::FrameGenerationDepthCopy> failed;
            assert(!Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,source,format,width,height,failed));
            assert(!failed);reject_allocation=false;
            const auto before=copies;
            assert(!Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,source,vk::Format::eR8Unorm,width,height,copy));
            assert(!Vulkan::FrameGeneration::FreezeDepth(device,allocator,command,source,format,0,height,copy));
            assert(copies==before);
            copy.reset();images.erase(source);images.erase(larger);++cases;
        }
    }
    assert(images.empty() && views.empty() && commands.empty());
    assert(copies==27 && barriers==54);
    std::printf("FG scene depth: PASS (%u cases, D32/D32S8/R32, UI overwrite reproduced, reuse, resize ownership, failure and recorded aspects/barriers)\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='fg-depth-') as temp:
    portable_headers = Path(temp) / 'include'
    portable_headers.mkdir()
    for directory in ('vulkan', 'vk_video'):
        shutil.copytree(headers/directory, portable_headers/directory)
    shutil.copy2(headers/'vma/vk_mem_alloc.h',portable_headers/'vk_mem_alloc.h')
    cpp = Path(temp) / 'test.cpp'
    executable = Path(temp) / 'test'
    cpp.write_text(HARNESS.replace('__METHODS__', methods))
    subprocess.run(['g++', '-std=c++23', '-O1', '-g', '-fsanitize=address,undefined',
        '-fno-omit-frame-pointer',
        '-I'+str(ROOT/'gpu/shadps4'), '-I'+str(portable_headers), str(cpp), '-o', str(executable)], check=True)
    import os
    subprocess.run([str(executable)],check=True,env=dict(os.environ,ASAN_OPTIONS='detect_leaks=0'))
