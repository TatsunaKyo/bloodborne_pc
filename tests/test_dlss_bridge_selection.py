"""Run the production ABI gate, bridge selection and SR initialization without NGX hardware."""
from pathlib import Path
import subprocess,tempfile,os
root=Path(__file__).resolve().parents[1];source=(root/'gpu/shadps4/video_core/renderer_vulkan/vk_dlss.cpp').read_text()
def fn(name):
 a=source.index(name);a=source.rfind('\n',0,a)+1;b=source.index('{',a)+1;depth=1
 while depth:depth+=(source[b]=='{')-(source[b]=='}');b+=1
 return source[a:b]
start=source.index('    if (!impl->api ||');end=source.index(' {',start);condition=source[start+8:end-1]
# The expression is taken verbatim from the constructor's if (...).
condition=source[start+len('    if ('):end-1]
text=r'''
#include "bbport_settings.h"
#include "bbport_dlss_bridge.h"
#include <cassert>
#include <cstdio>
#include <cstddef>
#include <memory>
#include <string>
#include <cwchar>
namespace BbSettings {Values values;Values& Get(){return values;}}
namespace vk {using Instance=VkInstance;using PhysicalDevice=VkPhysicalDevice;using Device=VkDevice;}
struct Dispatch {PFN_vkGetInstanceProcAddr vkGetInstanceProcAddr=nullptr;PFN_vkGetDeviceProcAddr vkGetDeviceProcAddr=nullptr;} dispatch;
#define VULKAN_HPP_DEFAULT_DISPATCHER dispatch
@BRIDGE@
struct LegacyApi {
 uint32_t abi=1;
 decltype(BbDlssApi::Configure) Configure=nullptr;
 decltype(BbDlssApi::InstanceExtensions) InstanceExtensions=nullptr;
 decltype(BbDlssApi::DeviceExtensions) DeviceExtensions=nullptr;
 decltype(BbDlssApi::Initialize) Initialize=nullptr;
 decltype(BbDlssApi::CreateFeature) CreateFeature=nullptr;
 decltype(BbDlssApi::Evaluate) Evaluate=nullptr;
 decltype(BbDlssApi::ReleaseFeature) ReleaseFeature=nullptr;
 decltype(BbDlssApi::Shutdown) Shutdown=nullptr;
};
static_assert(sizeof(LegacyApi)==offsetof(BbDlssApi,FrameGenMaxCount));
struct Dlss {
 struct Impl {
  const BbDlssApi* api;bool eligible=true,instance_ready=true,device_ready=true,initialized=false,available=false;int frame_gen_max=0;
  void Disable(const char*){eligible=available=false;}
 };
 std::unique_ptr<Impl> impl;
 explicit Dlss(const BbDlssApi* api):impl(std::make_unique<Impl>(Impl{api})){}
 bool Accepted()const{if(@CONDITION@)return false;return true;}
 void Initialize(vk::Instance,vk::PhysicalDevice,vk::Device);
};
@INITIALIZE@
unsigned calls=0;int max_frames=0;
int32_t initialize(VkInstance,VkPhysicalDevice,VkDevice,PFN_vkGetInstanceProcAddr,PFN_vkGetDeviceProcAddr){++calls;return 1;}
int32_t framegen(){return max_frames;}
int main(){
 auto old=std::make_unique<LegacyApi>();old->Initialize=initialize;
 Dlss sr(reinterpret_cast<const BbDlssApi*>(old.get()));assert(sr.Accepted());sr.Initialize({},{},{});assert(sr.impl->available && calls==1 && BbSettings::Get().dlssg_max_multiplier==1);
 BbDlssApi next{};next.abi=2;next.Initialize=initialize;next.FrameGenMaxCount=framegen;
 Dlss no_fg(&next);assert(no_fg.Accepted());no_fg.Initialize({},{},{});assert(no_fg.impl->available && no_fg.impl->frame_gen_max==0 && BbSettings::Get().dlssg_max_multiplier==1);
 max_frames=3;Dlss with_fg(&next);with_fg.Initialize({},{},{});assert(with_fg.impl->available && BbSettings::Get().dlssg_max_multiplier==4);
 next.abi=3;assert(!Dlss(&next).Accepted());assert(!Dlss(nullptr).Accepted());
 BbSettings::Get().startup_native_dlss=false;assert(!wcscmp(BridgeName(),L"bbport_dlss.dll"));
 BbSettings::Get().startup_native_dlss=true;assert(!wcscmp(BridgeName(),L"bbport_dlss_native.dll"));
 std::puts("PASS actual DLSS loader policy: ABI1 SR remains accepted; ABI2 SR works with FG unavailable; incompatible ABI rejected; native bridge loaded only for its startup family.");
}
'''
text=text.replace('@BRIDGE@',fn('const wchar_t* BridgeName(')).replace('@CONDITION@',condition).replace('@INITIALIZE@',fn('void Dlss::Initialize('))
with tempfile.TemporaryDirectory(prefix='dlss-abi-') as d:
 d=Path(d);cpp=d/'test.cpp';exe=d/'test';cpp.write_text(text)
 subprocess.run([*os.environ.get('CXX','g++').split(),'-std=c++20','-O1','-I'+str(root/'gpu/shim'),'-I'+str(root/'gpu/dlss_bridge'),'-I'+str(root/'out/test-headers'),str(cpp),'-o',str(exe)],check=True);subprocess.run([str(exe)],check=True,timeout=30)
