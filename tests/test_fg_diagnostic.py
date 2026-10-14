# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Exercise exact native FG readbacks with a recording backend and private export failures."""
import hashlib
import importlib.util
import json
from pathlib import Path
import os
import subprocess
import sys
import tempfile
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import fg_diagnostic as capture
spec=importlib.util.spec_from_file_location('fg_launcher',ROOT/'launcher/bbport_launcher_win.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)
source=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_frame_generation.cpp').read_text()
method=source[source.index('void FrameGeneration::CaptureDiagnostic('):source.index('void FrameGeneration::RetireCompleted()')]
HEADERS=ROOT/'out/test-headers'
HARNESS=r'''
#include "video_core/renderer_vulkan/vk_frame_generation.h"
#include "bbport_capture.h"
#include <vk_mem_alloc.h>
#include <cassert>
#include <cmath>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <locale>
#include <sstream>
#include <unordered_map>
#include <vector>
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
uintptr_t next_handle=10;
template<class T>T Handle(){return reinterpret_cast<T>(++next_handle);}
struct Pixels{unsigned width,height;vk::ImageLayout layout;std::vector<uint32_t> data;};
std::unordered_map<VkImage,Pixels> images;
std::unordered_map<VkBuffer,std::vector<uint32_t>> buffers;
std::vector<std::function<void()>> commands;
unsigned allocations{},destroyed{},barriers{},copies{},fail_at{};
bool host_visible{};
void Env(const char* key,const std::string& value){
#ifdef _WIN32
 _putenv_s(key,value.c_str());
#else
 setenv(key,value.c_str(),1);
#endif
}
extern "C" VkResult vmaCreateBuffer(VmaAllocator,const VkBufferCreateInfo* info,
 const VmaAllocationCreateInfo* flags,VkBuffer* buffer,VmaAllocation* allocation,VmaAllocationInfo* mapped){
 ++allocations;if(allocations==fail_at)return VK_ERROR_OUT_OF_HOST_MEMORY;
 assert(info->usage==VK_BUFFER_USAGE_TRANSFER_DST_BIT);
 assert(flags->flags&VMA_ALLOCATION_CREATE_MAPPED_BIT);
 *buffer=Handle<VkBuffer>();*allocation=Handle<VmaAllocation>();
 auto& data=buffers[*buffer];data.resize(info->size/4);
 mapped->pMappedData=data.data();return VK_SUCCESS;
}
extern "C" void vmaDestroyBuffer(VmaAllocator,VkBuffer buffer,VmaAllocation){assert(buffers.erase(buffer)==1);++destroyed;}
extern "C" VkResult vmaInvalidateAllocation(VmaAllocator,VmaAllocation,VkDeviceSize,VkDeviceSize){assert(host_visible);return VK_SUCCESS;}
VKAPI_ATTR void VKAPI_CALL Barrier(VkCommandBuffer,const VkDependencyInfo* info){
 ++barriers;assert(info->imageMemoryBarrierCount==3);
 if(info->memoryBarrierCount){
  assert(info->memoryBarrierCount==1);
  const auto& host=info->pMemoryBarriers[0];
  assert(host.srcStageMask==VK_PIPELINE_STAGE_2_TRANSFER_BIT && host.srcAccessMask==VK_ACCESS_2_TRANSFER_WRITE_BIT);
  assert(host.dstStageMask==VK_PIPELINE_STAGE_2_HOST_BIT && host.dstAccessMask==VK_ACCESS_2_HOST_READ_BIT);
  commands.push_back([]{host_visible=true;});
 }else commands.push_back([]{host_visible=false;});
 for(unsigned i=0;i<3;++i){const auto b=info->pImageMemoryBarriers[i];
  assert(b.srcQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED && b.dstQueueFamilyIndex==VK_QUEUE_FAMILY_IGNORED);
  assert(b.subresourceRange.aspectMask==VK_IMAGE_ASPECT_COLOR_BIT);
  commands.push_back([b]{auto& image=images.at(b.image);assert(VkImageLayout(image.layout)==b.oldLayout);image.layout=vk::ImageLayout(b.newLayout);});
 }
}
VKAPI_ATTR void VKAPI_CALL Copy(VkCommandBuffer,VkImage image,VkImageLayout layout,VkBuffer buffer,
 unsigned count,const VkBufferImageCopy* region){
 ++copies;assert(layout==VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL && count==1);
 assert(region->imageExtent.width==images.at(image).width && region->imageExtent.height==images.at(image).height);
 commands.push_back([image,buffer]{assert(images.at(image).layout==vk::ImageLayout::eTransferSrcOptimal);buffers.at(buffer)=images.at(image).data;});
}
namespace Vulkan {
class Scheduler {
public:std::vector<std::function<void()>> callbacks;
 void DeferPriorityOperation(std::function<void()> action){callbacks.push_back(std::move(action));}
};
FrameGeneration::Image::~Image(){}
__METHOD__
}
void Execute(Vulkan::Scheduler& scheduler){
 for(auto& command:commands)command();commands.clear();
 for(auto& callback:scheduler.callbacks)callback();scheduler.callbacks.clear();
}
int main(int argc,char** argv){
 const auto folder=std::filesystem::path(argv[1]);const bool reject=argc>2;
 std::filesystem::create_directories(folder);
 auto trigger=(folder/"trigger").string();Env("BB_FG_CAPTURE_DIR",folder.string());
 Vulkan::FrameGeneration::Snapshot snapshot;snapshot.width=8;snapshot.height=4;
 snapshot.source.render_width=4;snapshot.source.render_height=2;
 snapshot.source.near_plane=.01f;snapshot.source.vertical_fov=1;
 snapshot.source.projection={1,1,1,-.01f};snapshot.source.previous_projection=snapshot.source.projection;
 snapshot.depth.image=Handle<VkImage>();snapshot.motion.image=Handle<VkImage>();auto color=Handle<VkImage>();
 images.emplace(VkImage(vk::Image(snapshot.depth)),Pixels{4,2,vk::ImageLayout::eGeneral,std::vector<uint32_t>(8,0x3f000000)});
 images.emplace(VkImage(vk::Image(snapshot.motion)),Pixels{4,2,vk::ImageLayout::eGeneral,std::vector<uint32_t>(8,0xc0004400)});
 images.emplace(color,Pixels{8,4,vk::ImageLayout::ePresentSrcKHR,std::vector<uint32_t>(32,0xc18a0917)});
 VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdPipelineBarrier2=Barrier;
 VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdCopyImageToBuffer=Copy;
 Vulkan::Scheduler scheduler;BbCapture::FrameGenerationCamera camera;
 camera.motion_scale={.25f,.5f};camera.reset=true;
 for(unsigned i=0;i<16;++i)camera.clip_to_previous[i]=float(i);
 const vk::Device device{Handle<VkDevice>()};auto allocator=Handle<VmaAllocator>();
 const vk::CommandBuffer command{Handle<VkCommandBuffer>()};
 // Normal play does not allocate, copy, poll a trigger or alter layouts.
 Vulkan::FrameGeneration::CaptureDiagnostic(scheduler,device,allocator,command,snapshot,color,vk::Format::eA2B10G10R10UnormPack32,8,4,77,1,camera);
 assert(allocations==0 && commands.empty() && scheduler.callbacks.empty());
 Env("BB_FG_CAPTURE_TRIGGER",trigger);BbCapture::GeometryKey key;
 assert(!key.Press(false,false) && !key.Press(true,true) && key.Press(true,false));
 if(reject)fail_at=2;
 for(unsigned frame=0;frame<(reject?1:4);++frame){
  Vulkan::FrameGeneration::CaptureDiagnostic(scheduler,device,allocator,command,snapshot,color,
   frame%2?vk::Format::eB8G8R8A8Srgb:vk::Format::eA2B10G10R10UnormPack32,8,4,77+frame,1,camera);
  if(!reject){assert(!std::filesystem::exists(folder/("fg"+std::to_string(frame)+".json")));Execute(scheduler);}
 }
 if(reject){assert(buffers.empty() && destroyed==1 && copies==0 && barriers==0 && scheduler.callbacks.empty());}
 else {assert(buffers.empty() && destroyed==12 && copies==12 && barriers==8);
  const auto before=allocations;Vulkan::FrameGeneration::CaptureDiagnostic(scheduler,device,allocator,command,snapshot,color,vk::Format::eB8G8R8A8Srgb,8,4,90,1,camera);assert(allocations==before);
 }
 for(const auto& [image,pixels]:images)assert(pixels.layout==(image==color?vk::ImageLayout::ePresentSrcKHR:vk::ImageLayout::eGeneral));
 // Larger resolutions and changes cannot exceed the shared host budget.
 BbCapture::FrameGenerationRequest request;auto big=(folder/"big-trigger").string();std::ofstream(big).close();
 assert(!request.Poll(big.c_str(),32768,32768,32768,32768));
 BbCapture::FrameGenerationRequest changing;std::ofstream(big).close();
 auto first=changing.Poll(big.c_str(),1920,1080,3840,2160);assert(first && first->count==4);
 assert(!changing.Poll(big.c_str(),8192,8192,8192,8192));
 std::puts("PASS: production NVIDIA readback: actual HDR/SDR bytes/constants, delayed writes, exact layout restoration, allocation rollback, default-off and bounded capture.");
}
'''
with tempfile.TemporaryDirectory(prefix='workshop-fg-capture-') as temp:
 temp=Path(temp);cpp=temp/'capture.cpp';cpp.write_text(HARNESS.replace('__METHOD__',method))
 exe=temp/('capture.exe' if os.name=='nt' else 'capture')
 compiler=os.environ.get('CXX','g++')
 command=[compiler,'-std=c++20','-O1','-I',str(ROOT/'gpu/shim'),'-I',str(ROOT/'gpu/shadps4'),'-I',str(HEADERS),'-I',str(HEADERS/'vma'),str(cpp),'-o',str(exe)]
 if Path(compiler).stem.lower()=='cl':command=[compiler,'/nologo','/std:c++20','/EHsc','/I'+str(ROOT/'gpu/shim'),'/I'+str(ROOT/'gpu/shadps4'),'/I'+str(HEADERS),'/I'+str(HEADERS/'vma'),str(cpp),'/Fe:'+str(exe)]
 subprocess.run(command,check=True)
 session=temp/'session';native=session/'fg-inputs';native.mkdir(parents=True)
 subprocess.run([str(exe),str(native)],check=True)
 subprocess.run([str(exe),str(temp/'allocation-failure'),'reject'],check=True)
 for index in range(4):
  raw=json.loads((native/f'fg{index}.json').read_text());assert raw['submission_frame']==77+index and raw['reset']
  assert raw['clip_to_previous']==list(range(16)) and raw['motion_scale']==[.25,.5]
  assert (native/f'fg{index}_depth_4x2.raw').read_bytes()==bytes.fromhex('0000003f')*8
  assert (native/f'fg{index}_motion_4x2.raw').read_bytes()==bytes.fromhex('004400c0')*8
  assert (native/f'fg{index}_real_color_8x4.raw').read_bytes()==bytes.fromhex('17098ac1')*32
 port=temp/'port';port.mkdir();(port/'BUILD-IDENTITY.json').write_text(json.dumps({'version':'1.6-tatsunakyo.32','source_commit':'a'*40,'private_path':r'C:\Users\Private\build'}))
 (session/'session.log').write_text('GPU: test\npassword=secret-test\nGPU: good\nC:\\Users\\Private\\game\n')
 metadata={'revision':'1.6-tatsunakyo.32','nvidia_diagnostic':'inputs','ini':{'object_motion':'1','password':'bad'},'menu_at_exit':{'real_fps_limit':65,'frame_generation':'nvidia'}}
 with patch.object(capture,'detect_system',return_value={'os':{'system':'Windows'},'gpus':[{'model':'fixture RTX'}]}):
  result=capture.export_capture(session,port,metadata);assert result['status']=='captured' and result['complete_frames']==4,result
  archive=session/result['archive']
  with zipfile.ZipFile(archive) as bundle:
   assert bundle.testzip() is None
   integrity=json.loads(bundle.read('archive-integrity.json'))
   for name,record in integrity.items():
    data=bundle.read(name);assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
   text=bundle.read('session.log').decode();assert 'secret-test' not in text and 'Private' not in text
   assert 'private_path' not in bundle.read('build-identity.json').decode()
   assert 'password' not in bundle.read('session.json').decode()
  previous=archive.read_bytes()
  with patch.object(capture.zipfile,'ZipFile',side_effect=OSError('interrupted export')):
   assert capture.export_capture(session,port,metadata)['status']=='archive_failed'
  assert archive.read_bytes()==previous and not archive.with_suffix('.tmp').exists()
  # Partial, malformed and unrelated private files cannot look like complete captures.
  (native/'fg1_motion_4x2.raw').write_bytes(b'partial')
  (native/'fg2.json').write_text('{broken')
  (native/'save.dat').write_text('SAVE SECRET')
  (native/'fg3_real_color_8x4.raw').unlink()
  (native/'fg3_real_color_8x4.raw').symlink_to(native/'save.dat')
  result=capture.export_capture(session,port,metadata);assert result['status']=='incomplete' and result['complete_frames']==1,result
  with zipfile.ZipFile(archive) as bundle:
   assert 'fg-inputs/save.dat' not in bundle.namelist()
   assert 'fg-inputs/fg3_real_color_8x4.raw' not in bundle.namelist()
  empty=temp/'empty';empty.mkdir();assert capture.export_capture(empty,port,metadata)['status']=='no_frames'
 launcher.DATA_DIR=temp
 settings=dict(launcher.APP_DEFAULTS,draw_pipe='1',extra_env='BB_PREP_WORKERS=8 BB_VK_RECORD_THREAD=1 BB_COPY_THREADS=4')
 original=settings.copy()
 assert launcher.nvidia_diagnostic_settings(settings,[]) is settings
 for mode in ('inputs','generated-only'):
  selected=launcher.nvidia_diagnostic_settings(settings,['--play','--nvidia-diagnostic='+mode])
  diagnostic=launcher.DiagnosticSession(selected);env=diagnostic.environment(launcher.game_environment(selected))
  assert tuple(env[k] for k in ('BB_DRAW_PIPE','BB_PREP_WORKERS','BB_VK_RECORD_THREAD','BB_COPY_THREADS'))==('1','8','1','4')
  assert env['BB_FG_GENERATED_ONLY']==('1' if mode=='generated-only' else '0')
  assert 'BB_DUMP_TRIGGER' not in env and 'BB_GEOMETRY_CAPTURE' not in env
  diagnostic.finish(0)
 assert settings==original
print('PASS: NVIDIA diagnostic export: byte hashes/CRC, exact constants, privacy, partial/malformed/missing files, symlink exclusion, interrupted export preserves previous ZIP, one-run comparisons retain normal renderer/settings.')
