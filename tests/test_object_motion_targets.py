"""Execute production motion-target methods against a deferred mock Vulkan queue.

The R54 control reproduces allocation/drain churn. This checks ownership and
image selection; it does not measure hardware performance or game artifacts.
"""
from pathlib import Path
import os, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = '1f793cceb6bdc6acc91531caf0361b5fe47e6ce5'
CPP = r'''
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "video_core/renderer_vulkan/motion_history.h"
#include <cassert>
#include <functional>
#include <iostream>
#include <set>
#include <map>
using VmaAllocation=void*;
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
u64 serial=0,created=0,destroyed=0;
std::set<VkImage> live,pending;
std::map<VkImageView,VkImage> views;
VKAPI_ATTR VkResult VKAPI_CALL MakeView(VkDevice,const VkImageViewCreateInfo* info,const VkAllocationCallbacks*,VkImageView* out){
 assert(live.contains(info->image));*out=reinterpret_cast<VkImageView>(++serial);views[*out]=info->image;return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL FreeView(VkDevice,VkImageView view,const VkAllocationCallbacks*){assert(views.erase(view)==1);}
VKAPI_ATTR void VKAPI_CALL Barrier(VkCommandBuffer,const VkDependencyInfo* info){
 for(u32 i=0;i<info->imageMemoryBarrierCount;++i)assert(live.contains(info->pImageMemoryBarriers[i].image));
}
namespace VideoCore {struct UniqueImage {
 vk::Image handle{};
 UniqueImage()=default;UniqueImage(vk::Device,void*){}
 UniqueImage(const UniqueImage&)=delete;
 UniqueImage(UniqueImage&& other):handle(other.handle){other.handle=vk::Image{};}
 void Reset(){if(handle){assert(!pending.contains(VkImage(handle)));assert(live.erase(VkImage(handle))==1);++destroyed;handle=vk::Image{};}}
 UniqueImage& operator=(UniqueImage&& other){Reset();handle=other.handle;other.handle=vk::Image{};return *this;}
 ~UniqueImage(){Reset();}
 explicit operator bool()const{return bool(handle);}
 operator vk::Image()const{return handle;}
 void Create(const vk::ImageCreateInfo& info){assert(info.extent.width&&info.extent.height);handle=vk::Image(reinterpret_cast<VkImage>(++serial));live.insert(VkImage(handle));++created;}
};}
namespace BbStats {constexpr bool enabled=false;}
namespace Shader::MotionVectors {constexpr u32 Output=1;}
namespace Vulkan {
template<class T>T Check(vk::ResultValue<T> result){assert(result.result==vk::Result::eSuccess);return std::move(result.value);}
struct Instance {vk::Device GetDevice()const{return vk::Device(reinterpret_cast<VkDevice>(1));}void* GetAllocator()const{return nullptr;}};
struct Scheduler {
 std::vector<std::function<void(vk::CommandBuffer)>> work;u64 finishes=0;
 void Record(std::function<void(vk::CommandBuffer)> fn){work.push_back(std::move(fn));}
 void EndRendering(){}void Wait(u64){}
 void Finish(){for(auto& fn:work)fn(vk::CommandBuffer(reinterpret_cast<VkCommandBuffer>(1)));work.clear();pending.clear();++finishes;}
};
struct RenderState {struct Attachment {vk::ImageView image_view;vk::ImageLayout image_layout;bool is_clear;};std::array<Attachment,8> color_attachments{};u16 num_color_attachments=0;};
@CLASS@
ObjectMotion::ObjectMotion(const Instance& i,Scheduler& s):instance(i),scheduler(s){enabled=true;}
ObjectMotion::~ObjectMotion(){scheduler.Finish();}
@METHODS@
}
int main(){
 VULKAN_HPP_DEFAULT_DISPATCHER.vkCreateImageView=MakeView;
 VULKAN_HPP_DEFAULT_DISPATCHER.vkDestroyImageView=FreeView;
 VULKAN_HPP_DEFAULT_DISPATCHER.vkCmdPipelineBarrier2=Barrier;
 Vulkan::Instance instance;Vulkan::Scheduler scheduler;Vulkan::RenderState state;
 {
  Vulkan::ObjectMotion motion(instance,scheduler);
  for(unsigned frame=0;frame<1000;++frame){
   motion.OnFrameStart();
   for(auto [w,h]:{std::pair{1920u,1080u},{960u,540u},{1280u,720u}}){
    motion.Attach(state,w,h);assert(state.color_attachments[1].is_clear);
    pending.insert(views.at(VkImageView(state.color_attachments[1].image_view)));
   }
   bool valid=false;motion.PrepareRead(vk::CommandBuffer(reinterpret_cast<VkCommandBuffer>(1)),1920,1080,valid);
#ifdef CURRENT
   assert(valid);motion.Attach(state,1920,1080);assert(!state.color_attachments[1].is_clear);
#else
   assert(!valid);
#endif
  }
#ifdef CURRENT
  assert(created==3&&scheduler.finishes==0);
  motion.OnFrameStart();bool valid=true;motion.PrepareRead(vk::CommandBuffer(reinterpret_cast<VkCommandBuffer>(1)),1920,1080,valid);assert(!valid);
  motion.Attach(state,640,360);assert(created==4&&scheduler.finishes==0);
  motion.Attach(state,3840,2160);assert(created==5&&scheduler.finishes==1&&destroyed==1&&live.size()==4);
  std::cout<<"PASS: 1000 three-size frames create 3 targets with 0 drains; scene vectors retained; fifth-size eviction drains before destruction.\n";
#else
  assert(created==3000&&scheduler.finishes==2999);
  std::cout<<"R54 control: 3000 allocations, 2999 drains, scene vectors unavailable after size switches.\n";
#endif
 }
 assert(live.empty()&&views.empty());
}
'''

def method(text, name):
    start=text.index(name);end=text.index('{',start)+1;depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

def run(current, folder):
    prefix='gpu/shadps4/video_core/renderer_vulkan/vk_object_motion.'
    def read(ext):
        return (ROOT/(prefix+ext)).read_text() if current else subprocess.check_output(['git','show',BASE+':'+prefix+ext],cwd=ROOT,text=True)
    header,source=read('h'),read('cpp')
    declaration=header[header.index('class ObjectMotion {'):header.rindex('} // namespace')]
    names=['void ObjectMotion::OnFrameStart(',('ObjectMotion::Target&' if current else 'void')+' ObjectMotion::EnsureImage(', 'void ObjectMotion::Attach(', 'vk::ImageView ObjectMotion::PrepareRead(']
    code=CPP.replace('@CLASS@',declaration).replace('@METHODS@','\n'.join(method(source,n) for n in names))
    cpp=folder/('current.cpp' if current else 'control.cpp');cpp.write_text(code);exe=cpp.with_suffix('')
    command=[os.environ.get('CXX','g++'),'-std=c++20','-O1','-pthread','-I'+str(ROOT/'gpu/shadps4'),'-I'+str(ROOT/'out/test-headers')]
    if current:command+=['-DCURRENT']
    subprocess.run(command+[str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=60)

with tempfile.TemporaryDirectory(prefix='motion-targets-') as temporary:
    for current in (False,True):run(current,Path(temporary))
