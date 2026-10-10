// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo revision. NVIDIA API declarations retain their original license.
#include "bbport_nvidia.h"
#include "bbport_settings.h"
#include "bbport_background.h"
#include "bbport_latency.h"
#include "bbport_frame_metrics.h"
#include "video_core/renderer_vulkan/vk_presenter.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <deque>
#include <chrono>
#include <mutex>
#ifdef _WIN32
#include <windows.h>
#include <filesystem>
#include "sl_core_api.h"
#include "sl_dlss_g.h"
#include "sl_reflex.h"
#include "sl_pcl.h"
#include "sl_security.h"

namespace BbNvidia {
namespace {
std::mutex mutex;
std::atomic<bool> initialized{};
HMODULE module{}; // Kept loaded: Vulkan dispatch tables contain its functions.
vk::Device device;
PFun_slShutdown* shutdown_api;
PFun_slIsFeatureSupported* supported;
PFun_slGetFeatureFunction* feature;
PFun_slGetNewFrameToken* new_token;
PFun_slSetConstants* constants;
PFun_slSetTagForFrame* tags;
PFun_slDLSSGGetState* fg_state;
PFun_slDLSSGSetOptions* fg_options;
PFun_slReflexSleep* sleep_api;
PFun_slReflexSetOptions* reflex_options;
PFun_slReflexGetState* reflex_state;
PFun_slPCLSetMarker* marker_api;
sl::FrameToken* simulation_token;
uint32_t frame_index{};
bool rendering{}, fg_on{}, failed{};
std::atomic<bool> fg_supported{}, reflex_supported{};
vk::Semaphore latest_fence;
uint64_t latest_value{};
std::atomic<uint64_t> input_epoch{1};
uint32_t configured_generated{},configured_width{},configured_height{},configured_format{};
const sl::ViewportHandle viewport{0};
struct Flip { int index; int64_t argument; sl::FrameToken* token; };
std::deque<Flip> flips;
std::chrono::steady_clock::time_point latency_query{},latency_updated{};
uint64_t latency_frame{};
BbFrameMetrics::Counter frame_metrics;
template<class T> bool Import(T*& target, const char* name) {
    target=reinterpret_cast<T*>(GetProcAddress(module,name)); return target!=nullptr;
}
template<class T> bool Feature(T*& target, sl::Feature id, const char* name) {
    void* p{}; if (feature(id,name,p)!=sl::Result::eOk || !p) return false;
    target=reinterpret_cast<T*>(p); return true;
}
void Log(sl::LogType type,const char* message) {
    if (type==sl::LogType::eError || type==sl::LogType::eWarn)
        std::printf("NVIDIA Streamline: %s\n",message);
}
void Error(const sl::APIError&) {
    BbSettings::Get().nvidia_api_error=true;
}
void Mark(sl::PCLMarker marker, sl::FrameToken* token) {
    if (marker_api && token) marker_api(marker,*token);
}
bool Wanted() {
    const auto& s=BbSettings::Get();
    return (s.reflex!=0 || s.frame_generation==BbSettings::FrameGenerationNvidia ||
            (s.show_fps && s.show_latency)) &&
           (s.window_focused || s.background_mode==BbSettings::BackgroundRun);
}
void UpdateLatency() {
    auto& s=BbSettings::Get();
    if (!s.show_fps || !s.show_latency || !reflex_state || !Wanted()) {
        s.pc_latency_ms=-1.0f;return;
    }
    const auto now=std::chrono::steady_clock::now();
    if (now-latency_updated>std::chrono::milliseconds(500)) s.pc_latency_ms=-1.0f;
    if (now-latency_query<std::chrono::milliseconds(100)) return;
    latency_query=now;
    sl::ReflexState state;
    if (reflex_state(state)!=sl::Result::eOk || !state.latencyReportAvailable) {
        s.pc_latency_ms=-1.0f;return;
    }
    if (const auto sample=BbLatency::Latest(state.frameReport,latency_frame)) {
        latency_frame=sample->frame;latency_updated=now;s.pc_latency_ms=sample->milliseconds;
    }
}
void WaitLatestInputs() {
    if (latest_fence && latest_value && device) {
        const auto result=device.waitSemaphores({.semaphoreCount=1,.pSemaphores=&latest_fence,
                                                 .pValues=&latest_value},UINT64_MAX);
        if (result!=vk::Result::eSuccess) std::printf("NVIDIA FG retirement failed (%d)\n",int(result));
        latest_fence=nullptr;latest_value=0;
        ++input_epoch; // All older frame fences are completed and may now be destroyed by SL.
    }
}
void Off() {
    // Wait before SetOptions(Off), which may release the SDK's input semaphore.
    // Draw frames from an older epoch must not wait on a destroyed SDK handle.
    WaitLatestInputs();
    if (fg_options && fg_on) {
        sl::DLSSGOptions options; options.mode=sl::DLSSGMode::eOff;
        fg_options(viewport,options);
    }
    fg_on=false;
    auto& s=BbSettings::Get();
    s.frame_generation_cap_multiplier=0;
    s.nvidia_real_fps=s.nvidia_output_fps=-1.0f;
    frame_metrics.Reset();
    if (s.frame_generation==BbSettings::FrameGenerationNvidia) s.frame_generation_active=0;
}
using Matrix=std::array<float,16>;
Matrix View(const std::array<float,12>& view) {
    Matrix r{};std::copy(view.begin(),view.end(),r.begin());r[15]=1;return r;
}
Matrix Projection(const std::array<float,4>& p, bool inverse=false) {
    Matrix r{};
    if (inverse) {r[0]=1/p[0];r[5]=1/p[1];r[11]=1;r[14]=1/p[3];r[15]=-p[2]/p[3];}
    else {r[0]=p[0];r[5]=p[1];r[10]=p[2];r[11]=p[3];r[14]=1;}
    return r;
}
Matrix Multiply(const Matrix& a,const Matrix& b) {
    Matrix r{};for(int y=0;y<4;++y)for(int x=0;x<4;++x)for(int k=0;k<4;++k)r[y*4+x]+=a[y*4+k]*b[k*4+x];return r;
}
void Transpose(sl::float4x4& target,const Matrix& source) {
    Matrix r{};for(int y=0;y<4;++y)for(int x=0;x<4;++x)r[y*4+x]=source[x*4+y];
    std::memcpy(&target,r.data(),sizeof(r));
}
sl::Resource Resource(vk::Image image,vk::ImageView view,vk::Format format,
                      uint32_t w,uint32_t h,vk::ImageLayout layout) {
    sl::Resource r{sl::ResourceType::eTex2d,reinterpret_cast<void*>(VkImage(image)),nullptr,
        reinterpret_cast<void*>(VkImageView(view)),uint32_t(layout)};
    r.width=w;r.height=h;r.nativeFormat=uint32_t(format);r.mipLevels=1;r.arrayLayers=1;
    r.flags=0;r.usage=VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_STORAGE_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    return r;
}
}
void* VulkanLoader(void* native) {
    std::scoped_lock lock{mutex};
    if (module) return initialized ? reinterpret_cast<void*>(GetProcAddress(module,"vkGetInstanceProcAddr")) : native;
    wchar_t exe[32768]{};GetModuleFileNameW(nullptr,exe,32768);
    const auto folder=std::filesystem::path(exe).parent_path()/L"streamline";
    const auto dll=folder/L"sl.interposer.dll";
    if (!std::filesystem::exists(dll)) {
        if (BbSettings::Get().frame_generation==BbSettings::FrameGenerationNvidia)
            BbSettings::Get().frame_generation_problem="NVIDIA runtime is missing. Extract the complete revision ZIP, including bin/streamline.";
        return native;
    }
    if (!sl::security::verifyEmbeddedSignature(dll.c_str())) {
        std::puts("NVIDIA Streamline: signature verification failed; native Vulkan retained.");return native;
    }
    module=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    if (!module) return native;
    PFun_slInit* init{};
    if (!Import(init,"slInit") || !Import(shutdown_api,"slShutdown") ||
        !Import(supported,"slIsFeatureSupported") || !Import(feature,"slGetFeatureFunction") ||
        !Import(new_token,"slGetNewFrameToken") || !Import(constants,"slSetConstants") || !Import(tags,"slSetTagForFrame")) return native;
    const sl::Feature features[]={sl::kFeatureDLSS_G,sl::kFeatureReflex,sl::kFeaturePCL};
    const auto directory=folder.wstring();const wchar_t* paths[]={directory.c_str()};
    sl::Preferences pref;
    pref.pathsToPlugins=paths;pref.numPathsToPlugins=1;
    pref.featuresToLoad=features;pref.numFeaturesToLoad=3;
    pref.flags=sl::PreferenceFlags::eUseManualHooking|sl::PreferenceFlags::eDisableCLStateTracking|
               sl::PreferenceFlags::eUseFrameBasedResourceTagging;
    pref.renderAPI=sl::RenderAPI::eVulkan;pref.engineVersion="bbport-TatsunaKyo";
    pref.projectId="42359704-c9f3-4806-9fb5-d469000fdb8a";pref.logMessageCallback=Log;
    const auto result=init(pref,sl::kSDKVersion);
    const auto proc=reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(module,"vkGetInstanceProcAddr"));
    if (result!=sl::Result::eOk || !proc) {
        std::printf("NVIDIA Streamline init failed (%u); native Vulkan retained.\n",unsigned(result));
        if (result==sl::Result::eOk) shutdown_api();return native;
    }
    initialized=true;std::puts("NVIDIA Streamline 2.14.1: Vulkan manual hooks initialized.");return reinterpret_cast<void*>(proc);
}
void BindDevice(vk::PhysicalDevice physical,vk::Device dev) {
    if (!initialized) return;
    std::scoped_lock lock{mutex};
    if (device==dev) return; // Do not overwrite live API pointers during swapchain recreation.
    device=dev;
    sl::AdapterInfo adapter;adapter.vkPhysicalDevice=reinterpret_cast<void*>(VkPhysicalDevice(physical));
    fg_supported=supported(sl::kFeatureDLSS_G,adapter)==sl::Result::eOk &&
        Feature(fg_state,sl::kFeatureDLSS_G,"slDLSSGGetState") && Feature(fg_options,sl::kFeatureDLSS_G,"slDLSSGSetOptions");
    reflex_supported=supported(sl::kFeatureReflex,adapter)==sl::Result::eOk &&
        Feature(sleep_api,sl::kFeatureReflex,"slReflexSleep") && Feature(reflex_options,sl::kFeatureReflex,"slReflexSetOptions") &&
        Feature(reflex_state,sl::kFeatureReflex,"slReflexGetState") && Feature(marker_api,sl::kFeaturePCL,"slPCLSetMarker");
    sl::ReflexState state;
    reflex_supported=reflex_supported && reflex_state(state)==sl::Result::eOk && state.lowLatencyAvailable;
    BbSettings::Get().nvidia_fg_supported=fg_supported && reflex_supported;
    BbSettings::Get().reflex_supported=reflex_supported.load();
    if (fg_supported) {
        sl::DLSSGState state;
        if (fg_state(viewport,state,nullptr)==sl::Result::eOk)
            BbSettings::Get().nvidia_max_generated=state.numFramesToGenerateMax;
    }
    std::printf("NVIDIA Vulkan: FG supported=%d, Reflex supported=%d\n",int(fg_supported),int(reflex_supported));
}
void BeginRender() {
    if (!initialized || !reflex_supported || !Wanted()) return;
    std::scoped_lock lock{mutex};
    if (!simulation_token) {const uint32_t id=++frame_index;new_token(simulation_token,&id);Mark(sl::PCLMarker::eSimulationStart,simulation_token);}
    if (!rendering) {Mark(sl::PCLMarker::eSimulationEnd,simulation_token);Mark(sl::PCLMarker::eRenderSubmitStart,simulation_token);rendering=true;}
}
void QueueFlip(int index,int64_t argument) {
    if (!initialized || !reflex_supported || !Wanted()) return;
    BeginRender();std::scoped_lock lock{mutex};
    flips.push_back({index,argument,simulation_token});
}
void CancelFlip(int index,int64_t argument) {
    if (!initialized) return;std::scoped_lock lock{mutex};
    std::erase_if(flips,[&](const Flip& f){return f.index==index && f.argument==argument;});
}
void NextSimulation() {
    if (!initialized || !reflex_supported) return;
    sl::FrameToken* next{};
    {
        std::scoped_lock lock{mutex};
        sl::ReflexOptions options;
        const auto& s=BbSettings::Get();
        const bool low_latency=Wanted() && (s.reflex!=0 || s.frame_generation==BbSettings::FrameGenerationNvidia);
        options.mode=low_latency ? s.reflex==2 ? sl::ReflexMode::eLowLatencyWithBoost : sl::ReflexMode::eLowLatency : sl::ReflexMode::eOff;
        // Preserve the real-frame limiter in VideoOut. Passing its 75 directly
        // as a display limiter would incorrectly cap FG to 75 total FPS.
        options.frameLimitUs=0;
        if (reflex_options(options)!=sl::Result::eOk) return;
        if (!Wanted()) {simulation_token=nullptr;rendering=false;BbSettings::Get().pc_latency_ms=-1.0f;return;}
        const uint32_t id=++frame_index;
        if (new_token(next,&id)!=sl::Result::eOk || !next) return;
    }
    // Never sleep on Liverpool's EOP thread or while holding m_submit_lock.
    // Previous render submission and present markers must be able to progress.
    sleep_api(*next);
    std::scoped_lock lock{mutex};
    if (!Wanted()) {sl::ReflexOptions options;options.mode=sl::ReflexMode::eOff;reflex_options(options);simulation_token=nullptr;rendering=false;return;}
    simulation_token=next;rendering=false;Mark(sl::PCLMarker::eSimulationStart,next);
}
void FinishRender(Vulkan::Frame* frame,int index,int64_t argument) {
    frame->nvidia_token=nullptr;
    if (!initialized) return;std::scoped_lock lock{mutex};
    const auto it=std::find_if(flips.begin(),flips.end(),[&](const Flip& f){return f.index==index && f.argument==argument;});
    if (it!=flips.end()) {frame->nvidia_token=it->token;Mark(sl::PCLMarker::eRenderSubmitEnd,it->token);flips.erase(it);}
}
void BeforePresent(Vulkan::Frame* frame,vk::CommandBuffer command,vk::Image image,vk::ImageView view,
                   vk::Format format,uint32_t buffers,bool game_frame) {
    if (!initialized) return;std::scoped_lock lock{mutex};
    auto& s=BbSettings::Get();auto* token=static_cast<sl::FrameToken*>(frame->nvidia_token);
    const auto snapshot=frame->frame_generation;
    if (s.frame_generation!=BbSettings::FrameGenerationNvidia) {Off();failed=false;s.nvidia_api_error=false;}
    if (s.frame_generation==BbSettings::FrameGenerationNvidia && (!fg_supported || !reflex_supported))
        s.frame_generation_problem="NVIDIA FG requires a supported GPU/driver and Hardware-accelerated GPU scheduling. Real frames are kept.";
    if (!game_frame || !Wanted() || !token || !snapshot || !fg_supported || !reflex_supported || failed || s.nvidia_api_error) {
        if (s.frame_generation==BbSettings::FrameGenerationNvidia && fg_supported && reflex_supported && !failed) {
            s.frame_generation_problem=s.nvidia_api_error ? "NVIDIA FG reported an API error. Turn FG off and on to retry; see last_run.log." :
                !Wanted() ? "NVIDIA FG is suspended while the game is in the background." :
                !game_frame ? "NVIDIA FG is waiting for a new game frame." :
                !token ? "NVIDIA FG is missing the frame's submission token; see last_run.log." :
                "NVIDIA FG is waiting for scene depth and motion vectors.";
        }
        Off();if (s.nvidia_api_error) {failed=true;s.frame_generation_problem="NVIDIA FG reported an API error. Turn FG off and on to retry; see last_run.log.";}
        Mark(sl::PCLMarker::ePresentStart,token);return;
    }
    if (s.frame_generation!=BbSettings::FrameGenerationNvidia) {Mark(sl::PCLMarker::ePresentStart,token);return;}
    const auto& source=snapshot->source;
    if (source.projection[0]==0 || source.projection[1]==0 || source.projection[3]==0) {
        s.frame_generation_problem="NVIDIA FG is waiting for a valid scene camera.";
        Off();Mark(sl::PCLMarker::ePresentStart,token);return;
    }
    const uint32_t generated=uint32_t(std::clamp(s.nvidia_generated_frames.load(),1,
        std::max(1,s.nvidia_max_generated.load())));
    if (fg_on && (configured_generated!=generated || configured_width!=snapshot->width ||
        configured_height!=snapshot->height || configured_format!=uint32_t(format))) Off();
    sl::DLSSGOptions options;options.mode=sl::DLSSGMode::eOn;options.numFramesToGenerate=generated;
    options.numBackBuffers=buffers;options.mvecDepthWidth=source.render_width;options.mvecDepthHeight=source.render_height;
    options.colorWidth=snapshot->width;options.colorHeight=snapshot->height;options.colorBufferFormat=uint32_t(format);
    options.mvecBufferFormat=VK_FORMAT_R16G16_SFLOAT;options.depthBufferFormat=VK_FORMAT_R32_SFLOAT;
    options.queueParallelismMode=sl::DLSSGQueueParallelismMode::eBlockPresentingClientQueue;options.onErrorCallback=Error;
    sl::Constants c;
    const auto p=Projection(source.projection),ip=Projection(source.projection,true);
    const auto pp=Projection(source.previous_projection),ipp=Projection(source.previous_projection,true);
    Transpose(c.cameraViewToClip,p);Transpose(c.clipToCameraView,ip);
    Transpose(c.clipToPrevClip,Multiply(Multiply(Multiply(pp,View(source.previous_view)),View(source.inverse_view)),ip));
    Transpose(c.prevClipToClip,Multiply(Multiply(Multiply(p,View(source.view)),View(source.previous_inverse_view)),ipp));
    c.jitterOffset={source.jitter[0],source.jitter[1]};c.mvecScale={1.0f/source.render_width,1.0f/source.render_height};
    c.cameraPos={source.inverse_view[3],source.inverse_view[7],source.inverse_view[11]};
    c.cameraRight={source.inverse_view[0],source.inverse_view[4],source.inverse_view[8]};
    c.cameraUp={source.inverse_view[1],source.inverse_view[5],source.inverse_view[9]};
    c.cameraFwd={source.inverse_view[2],source.inverse_view[6],source.inverse_view[10]};
    c.cameraNear=source.near_plane;c.cameraFar=3000;c.cameraFOV=source.vertical_fov;
    c.cameraAspectRatio=float(source.render_width)/source.render_height;c.depthInverted=sl::eFalse;
    c.cameraMotionIncluded=sl::eTrue;c.motionVectors3D=sl::eFalse;c.reset=source.reset || !fg_on ? sl::eTrue : sl::eFalse;
    auto depth=Resource(vk::Image(snapshot->depth),*snapshot->depth_view,vk::Format::eR32Sfloat,source.render_width,source.render_height,vk::ImageLayout::eGeneral);
    auto motion=Resource(vk::Image(snapshot->motion),*snapshot->motion_view,vk::Format::eR16G16Sfloat,source.render_width,source.render_height,vk::ImageLayout::eGeneral);
    auto color=Resource(image,view,format,snapshot->width,snapshot->height,vk::ImageLayout::ePresentSrcKHR);
    color.usage=VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT;
    color.internalFlags=sl::Resource::eVulkanSwapChainImage;
    sl::ResourceTag inputs[]={
        {&depth,sl::kBufferTypeDepth,sl::ResourceLifecycle::eValidUntilPresent},
        {&motion,sl::kBufferTypeMotionVectors,sl::ResourceLifecycle::eValidUntilPresent},
        {&color,sl::kBufferTypeBackbuffer,sl::ResourceLifecycle::eValidUntilPresent}};
    const auto options_result=fg_options(viewport,options);
    const auto constants_result=constants(c,*token,viewport);
    const auto tags_result=tags(*token,viewport,inputs,3,reinterpret_cast<sl::CommandBuffer*>(VkCommandBuffer(command)));
    if (options_result!=sl::Result::eOk || constants_result!=sl::Result::eOk || tags_result!=sl::Result::eOk) {
        std::printf("NVIDIA FG: options=%u, constants=%u, tags=%u\n",unsigned(options_result),unsigned(constants_result),unsigned(tags_result));
        fg_on=options_result==sl::Result::eOk;
        Off();failed=true;s.frame_generation_problem="NVIDIA FG input/options failed. Real frames are kept; see last_run.log.";
    } else {
        if (!fg_on) frame_metrics.Reset();
        fg_on=true;s.frame_generation_problem=nullptr;
        s.frame_generation_cap_multiplier=int(generated+1);
        configured_generated=generated;configured_width=snapshot->width;
        configured_height=snapshot->height;configured_format=uint32_t(format);
    }
    Mark(sl::PCLMarker::ePresentStart,token);
}
bool Present(Vulkan::Frame* frame,const std::function<bool()>& present) {
    if (!initialized) return present();
    // Serialize QueuePresent with GetState, SetOptions, focus and window changes.
    std::scoped_lock lock{mutex};
    const bool presented=present();
    Mark(sl::PCLMarker::ePresentEnd,static_cast<sl::FrameToken*>(frame->nvidia_token));
    UpdateLatency();
    if (fg_state && fg_on) {
        sl::DLSSGState state;
        const auto result=fg_state(viewport,state,nullptr);
        if (result==sl::Result::eOk) {
            auto& s=BbSettings::Get();
            s.nvidia_max_generated=state.numFramesToGenerateMax;
            frame_metrics.Output(state.numFramesActuallyPresented);
            if (presented && frame_metrics.Present(true)) {
                const auto measured=frame_metrics.Get();
                s.nvidia_real_fps=measured.real_fps;s.nvidia_output_fps=measured.output_fps;
                s.frame_generation_active=int(std::clamp(measured.multiplier,1u,state.numFramesToGenerateMax+1));
            }
            frame->nvidia_fence=vk::Semaphore(reinterpret_cast<VkSemaphore>(state.inputsProcessingCompletionFence));
            frame->nvidia_fence_value=state.lastPresentInputsProcessingCompletionFenceValue;
            frame->nvidia_fence_epoch=input_epoch;
            latest_fence=frame->nvidia_fence;latest_value=frame->nvidia_fence_value;
            const bool ok=state.status==sl::DLSSGStatus::eOk && !BbSettings::Get().nvidia_api_error;
            if (!ok) {
                std::printf("NVIDIA FG status=0x%x, API error=%d\n",unsigned(state.status),int(BbSettings::Get().nvidia_api_error.load()));
                Off();failed=true;BbSettings::Get().frame_generation_problem="NVIDIA FG is unavailable for the current GPU/driver/output. Real frames are kept; see last_run.log.";
            }
        } else {
            // Without an ownership fence, do not return these images for reuse.
            const auto idle=device.waitIdle();
            std::printf("NVIDIA FG GetState failed (%u), GPU drain=%d\n",unsigned(result),int(idle));
            ++input_epoch;latest_fence=nullptr;latest_value=0;
            Off();failed=true;
            BbSettings::Get().frame_generation_problem="NVIDIA FG ownership query failed. Real frames are kept; see last_run.log.";
        }
    }
    return presented;
}
void WaitForInputs(Vulkan::Frame* frame) {
    std::scoped_lock lock{mutex};
    if (frame->nvidia_fence_epoch==input_epoch && frame->nvidia_fence && frame->nvidia_fence_value && device) {
        const auto sem=frame->nvidia_fence;const auto value=frame->nvidia_fence_value;
        const auto result=device.waitSemaphores({.semaphoreCount=1,.pSemaphores=&sem,.pValues=&value},UINT64_MAX);
        if (result!=vk::Result::eSuccess) std::printf("NVIDIA FG input fence wait failed (%d)\n",int(result));
    }
    frame->nvidia_fence=nullptr;frame->nvidia_fence_value=0;frame->nvidia_fence_epoch=0;
}
void BeforeSwapchainChange() {
    if (!initialized) return;std::scoped_lock lock{mutex};Off();
    // Release latency scheduling before the background gate parks GPU workers.
    // NextSimulation rechecks focus after any sleep already in progress.
    if (!Wanted() && reflex_supported && reflex_options) {
        sl::ReflexOptions options;options.mode=sl::ReflexMode::eOff;
        reflex_options(options);
    }
}
void Shutdown() {
    if (!initialized) return;BeforeSwapchainChange();std::scoped_lock lock{mutex};
    shutdown_api();initialized=false;simulation_token=nullptr;flips.clear();device=nullptr;
}
}
#else
namespace BbNvidia {
void* VulkanLoader(void* native) {return native;}
void BindDevice(vk::PhysicalDevice,vk::Device) {}
void Shutdown() {}
void BeginRender() {}
void QueueFlip(int,int64_t) {}
void CancelFlip(int,int64_t) {}
void NextSimulation() {}
void FinishRender(Vulkan::Frame*,int,int64_t) {}
void BeforePresent(Vulkan::Frame*,vk::CommandBuffer,vk::Image,vk::ImageView,vk::Format,uint32_t,bool) {}
bool Present(Vulkan::Frame*,const std::function<bool()>& present) {return present();}
void WaitForInputs(Vulkan::Frame*) {}
void BeforeSwapchainChange() {}
}
#endif
