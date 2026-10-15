// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// TatsunaKyo revision. NVIDIA API declarations retain their original license.
#include "bbport_hitch.h"
#include "bbport_nvidia.h"
#include "bbport_nvidia_preset.h"
#include "bbport_nvidia_profile.h"
#include "bbport_settings.h"
#include "bbport_background.h"
#include "bbport_latency.h"
#include "bbport_frame_metrics.h"
#include "bbport_legacy_gpu.h"
#include "core/emulator_settings.h"
#include "video_core/renderer_vulkan/vk_presenter.h"
#include "video_core/renderer_vulkan/vk_scheduler.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <deque>
#include <chrono>
#include <mutex>
#include <tuple>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#include <wincrypt.h>
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
TokenPool<sl::MAX_FRAMES_IN_FLIGHT> token_pool;
std::condition_variable simulation_ready;
Token simulation_token;
uint32_t frame_index{};
bool rendering{}, simulation_sleeping{}, simulation_pending{}, fg_on{}, failed{};
bool input_queues_parallel{};
// Publish the cap and multiplier together. VideoOut only yields its limiter
// after the driver has accepted that exact foreground pacing policy.
std::atomic<uint64_t> pacing_policy{};
sl::ReflexOptions applied_reflex_options;
bool reflex_options_applied{};
std::atomic<bool> fg_supported{}, reflex_supported{};
vk::Semaphore latest_fence;
uint64_t latest_value{};
std::atomic<uint64_t> input_epoch{1};
uint32_t configured_generated{},configured_width{},configured_height{},configured_format{};
const sl::ViewportHandle viewport{0};
struct Flip { int index; int64_t argument; Token token; };
std::deque<Flip> flips;
std::chrono::steady_clock::time_point latency_query{},latency_updated{};
uint64_t latency_frame{};
BbFrameMetrics::Counter frame_metrics;
HMODULE nvapi_module{};
using NvapiQuery=void* (__cdecl*)(uint32_t);
using NvapiInitialize=int (__cdecl*)();
using NvapiGetOverride=int (__cdecl*)(void*);
NvapiGetOverride get_override{};
NvapiQuery nvapi_query{};
unsigned profile_poll{};
NvapiInitialize nvapi_unload{};
bool nvapi_attempted{};
Preset::Observer preset_observer;
void UpdatePreset() {
    auto& s=BbSettings::Get();
    if (s.frame_generation!=BbSettings::FrameGenerationNvidia) {
        s.nvidia_fg_reported_preset=-1;s.nvidia_fg_preset_status=0;s.nvidia_fg_feedback=0;return;
    }
    // Keep observing initialization failures too; a failed model must not hide
    // its driver error merely because it never reached an active multiplier.
    if (!nvapi_attempted) {
        nvapi_attempted=true;
        nvapi_module=LoadLibraryExW(L"nvapi64.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
        const auto query=nvapi_module ? reinterpret_cast<NvapiQuery>(GetProcAddress(nvapi_module,"nvapi_QueryInterface")) : nullptr;
        const auto init=query ? reinterpret_cast<NvapiInitialize>(query(0x0150e828)) : nullptr;
        const auto unload=query ? reinterpret_cast<NvapiInitialize>(query(0xd22bdd7e)) : nullptr;
        if (init && unload && init()==0) {
            nvapi_unload=unload;nvapi_query=query;
            get_override=reinterpret_cast<NvapiGetOverride>(query(0x3fd96fba));
        }
    }
    if (nvapi_query && profile_poll++%10==0) {
        const int profile=Preset::Drs::ReadPreset(nvapi_query);
        if (s.nvidia_fg_profile_preset!=profile)
            std::printf("NVIDIA FG profile preference: preset=%d (configuration only)\n",profile);
        s.nvidia_fg_profile_preset=profile;
    }
    if (!get_override) return;
    Preset::DriverState state{};
    const int result=Preset::ReadState(get_override,GetCurrentProcessId(),state);
    const int reported=result==0 && s.frame_generation_active>1 ? Preset::Reported(state) : -1;
    const int status=result==0 && (state.fg&Preset::ErrorMask) ? 2 : reported>=0 ? 1 : 0;
    if (s.nvidia_fg_reported_preset!=reported || s.nvidia_fg_preset_status!=status ||
        s.nvidia_fg_query_result!=result || s.nvidia_fg_feedback!=state.fg)
        std::printf("NVIDIA FG driver feedback: preset=%d, status=%d, flags=0x%llx, API=%d\n",
                    reported,status,static_cast<unsigned long long>(state.fg),result);
    s.nvidia_fg_feedback=result==0 ? state.fg : 0;
    s.nvidia_fg_query_result=result;
    s.nvidia_fg_reported_preset=reported;s.nvidia_fg_preset_status=status;
}
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
void Mark(sl::PCLMarker marker, const Token& token) {
    if (marker_api && token) marker_api(marker,*static_cast<sl::FrameToken*>(token->native));
}
bool ApplyReflexOptions(const sl::ReflexOptions& options) {
    if (reflex_options_applied && options.mode==applied_reflex_options.mode &&
        options.frameLimitUs==applied_reflex_options.frameLimitUs) return true;
    if (reflex_options(options)!=sl::Result::eOk) return false;
    applied_reflex_options=options;reflex_options_applied=true;
    return true;
}
bool Wanted() {
    const auto& s=BbSettings::Get();
    return (s.reflex!=0 || s.frame_generation==BbSettings::FrameGenerationNvidia ||
            (s.show_fps && s.show_latency)) &&
           (s.window_focused || s.background_mode==BbSettings::BackgroundRun);
}
Token NewSimulationToken(std::unique_lock<std::mutex>& lock) {
    if (!token_pool.WaitAvailable(lock, [] { return initialized && Wanted(); })) return {};
    const uint32_t id=frame_index+1;
    auto token=token_pool.Acquire(id, [](uint32_t value)->void* {
        sl::FrameToken* native{};
        return new_token(native,&value)==sl::Result::eOk ? native : nullptr;
    });
    if (token) frame_index=id;
    return token;
}
bool BeginRenderLocked(std::unique_lock<std::mutex>& lock) {
    simulation_ready.wait(lock, [] {
        return (!simulation_sleeping && !simulation_pending) || !initialized;
    });
    if (!initialized || !reflex_supported || !Wanted()) return false;
    if (!simulation_token) {
        simulation_token=NewSimulationToken(lock);
        if (!simulation_token) return false;
        Mark(sl::PCLMarker::eSimulationStart,simulation_token);
    }
    if (!rendering) {
        Mark(sl::PCLMarker::eSimulationEnd,simulation_token);
        Mark(sl::PCLMarker::eRenderSubmitStart,simulation_token);
        rendering=true;
    }
    return true;
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
    if (!initialized || !Wanted()) {s.pc_latency_ms=-1.0f;return;}
    if (const auto sample=BbLatency::Latest(state.frameReport,latency_frame)) {
        latency_frame=sample->frame;latency_updated=now;s.pc_latency_ms=sample->milliseconds;
    }
}
void UpdateTelemetry() {
    // GetLatencyReports is diagnostic driver IO. Keep it off QueuePresent and
    // outside the mutex needed by BeginRender/NextSimulation. The observer is
    // joined before slShutdown, so the imported function stays alive throughout.
    if (!initialized) return;
    UpdateLatency();
    static auto next_preset=std::chrono::steady_clock::time_point{};
    const auto now=std::chrono::steady_clock::now();
    if (now>=next_preset) {
        next_preset=now+std::chrono::seconds(1);
        UpdatePreset();
    }
    static auto next_cadence=std::chrono::steady_clock::time_point{};
    if (Wanted() && now>=next_cadence) {
        next_cadence=now+std::chrono::seconds(5);
        BbHitch::ReportCadence(BbSettings::Get().nvidia_output_fps);
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
    pacing_policy=0;
    if (reflex_options_applied && applied_reflex_options.frameLimitUs &&
        reflex_options && reflex_supported) {
        sl::ReflexOptions options;
        const auto& s=BbSettings::Get();
        const bool low_latency=Wanted() && (s.reflex!=0 || s.frame_generation==BbSettings::FrameGenerationNvidia);
        options.mode=low_latency ? s.reflex==2 ? sl::ReflexMode::eLowLatencyWithBoost : sl::ReflexMode::eLowLatency : sl::ReflexMode::eOff;
        ApplyReflexOptions(options); // Remove the output interval before FG changes mode.
    }
    // Wait before SetOptions(Off), which may release the SDK's input semaphore.
    // Draw frames from an older epoch must not wait on a destroyed SDK handle.
    WaitLatestInputs();
    if (fg_options && fg_on) {
        sl::DLSSGOptions options; options.mode=sl::DLSSGMode::eOff;
        fg_options(viewport,options);
    }
    fg_on=false;input_queues_parallel=false;
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
void PreloadMod() {
    auto& s=BbSettings::Get();
    if (!s.startup_nvidia_fg_mod || s.frame_generation!=BbSettings::FrameGenerationNvidia) return;
    // A private native probe must precede all third-party code and Streamline checks.
    // Never trust a spoofed adapter name or a launcher environment flag here.
    const auto vulkan=LoadLibraryExW(L"vulkan-1.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    const auto get=vulkan ? reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(vulkan,"vkGetInstanceProcAddr")) : nullptr;
    const auto create=get ? reinterpret_cast<PFN_vkCreateInstance>(get(nullptr,"vkCreateInstance")) : nullptr;
    VkApplicationInfo app{VK_STRUCTURE_TYPE_APPLICATION_INFO};app.apiVersion=VK_API_VERSION_1_3;
    VkInstanceCreateInfo info{VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO};info.pApplicationInfo=&app;
    VkInstance instance{};bool eligible=false;
    if (create && create(&info,nullptr,&instance)==VK_SUCCESS) {
        const auto enumerate=reinterpret_cast<PFN_vkEnumeratePhysicalDevices>(get(instance,"vkEnumeratePhysicalDevices"));
        const auto properties=reinterpret_cast<PFN_vkGetPhysicalDeviceProperties>(get(instance,"vkGetPhysicalDeviceProperties"));
        const auto memory=reinterpret_cast<PFN_vkGetPhysicalDeviceMemoryProperties>(get(instance,"vkGetPhysicalDeviceMemoryProperties"));
        const auto destroy=reinterpret_cast<PFN_vkDestroyInstance>(get(instance,"vkDestroyInstance"));
        uint32_t count{};
        if (enumerate && properties && memory && enumerate(instance,&count,nullptr)==VK_SUCCESS && count) {
            std::vector<VkPhysicalDevice> devices(count);
            if (enumerate(instance,&count,devices.data())==VK_SUCCESS) {
                const auto score=[&](VkPhysicalDevice gpu) {
                    VkPhysicalDeviceProperties p{};VkPhysicalDeviceMemoryProperties m{};properties(gpu,&p);memory(gpu,&m);
                    uint64_t heap{};
                    for (uint32_t i=0;i<m.memoryHeapCount;++i)
                        if (m.memoryHeaps[i].flags&VK_MEMORY_HEAP_DEVICE_LOCAL_BIT) heap=std::max<uint64_t>(heap,m.memoryHeaps[i].size);
                    return std::tuple{p.apiVersion>=VK_API_VERSION_1_3,p.deviceType==VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU,
                                      p.deviceType!=VK_PHYSICAL_DEVICE_TYPE_CPU,heap};
                };
                uint32_t selected=0;bool valid=true;
                if (const char* id=std::getenv("BB_GPU_ID"); id && std::atoi(id)>=0) {
                    char* end{};const auto index=std::strtoul(id,&end,10);
                    valid=end && !*end && index<count;if (valid) selected=uint32_t(index);
                } else for (uint32_t i=1;i<count;++i) if (score(devices[i])>score(devices[selected])) selected=i;
                if (valid) {
                    VkPhysicalDeviceProperties p{};properties(devices[selected],&p);
                    eligible=bb_dlssg_mod_gpu(p.vendorID,p.deviceName);
                    std::printf("DLSSG mod: real selected adapter %s (0x%x), eligible=%d\n",p.deviceName,p.vendorID,int(eligible));
                }
            }
        }
        if (destroy) destroy(instance,nullptr);
    }
    if (vulkan) FreeLibrary(vulkan);
    if (!eligible) {
        s.nvidia_fg_mod_status="Mod skipped: the selected GPU could not be verified as GeForce RTX 20/30. Original NVIDIA path retained.";return;
    }
    wchar_t exe[32768]{};GetModuleFileNameW(nullptr,exe,32768);
    const auto folder=std::filesystem::path(exe).parent_path()/L"mods"/L"dlssg";
    std::error_code error;
    auto dll=folder/L"dlssg_sm86.dll"; // Explicit user-supplied provider; keep its companions here.
    if (!std::filesystem::is_regular_file(dll,error)) dll=folder/L"rtx-encore.asi";
    if (!std::filesystem::is_regular_file(dll,error)) {
        s.nvidia_fg_mod_status="Mod missing: launch through the launcher to prepare it. Original NVIDIA path retained.";return;
    }
    if (dll.filename()==L"rtx-encore.asi") {
        HCRYPTPROV provider{};HCRYPTHASH hash{};
        HANDLE file=CreateFileW(dll.c_str(),GENERIC_READ,FILE_SHARE_READ,nullptr,OPEN_EXISTING,FILE_ATTRIBUTE_NORMAL,nullptr);
        bool ok=file!=INVALID_HANDLE_VALUE && CryptAcquireContextW(&provider,nullptr,nullptr,PROV_RSA_AES,CRYPT_VERIFYCONTEXT) &&
                CryptCreateHash(provider,CALG_SHA_256,0,0,&hash);
        std::array<unsigned char,65536> buffer{};DWORD count{};
        while (ok) {
            ok=ReadFile(file,buffer.data(),DWORD(buffer.size()),&count,nullptr);
            if (!ok || !count) break;
            ok=CryptHashData(hash,buffer.data(),count,0);
        }
        std::array<unsigned char,32> digest{};DWORD length=DWORD(digest.size());
        ok=ok && CryptGetHashParam(hash,HP_HASHVAL,digest.data(),&length,0) && length==digest.size();
        constexpr unsigned char expected[]={0xb6,0xa3,0x67,0xfd,0x41,0x03,0xf3,0x62,0x90,0xcc,0xf4,0x64,0xf5,0x04,0x86,0xab,
            0x72,0x83,0x26,0x4b,0x8c,0x0c,0x15,0x58,0xa1,0x97,0x61,0x5c,0xf0,0x1b,0x13,0xb0};
        ok=ok && std::equal(digest.begin(),digest.end(),expected);
        if (hash) CryptDestroyHash(hash);if (provider) CryptReleaseContext(provider,0);
        if (file!=INVALID_HANDLE_VALUE) CloseHandle(file);
        if (!ok) {s.nvidia_fg_mod_status="Mod checksum rejected. Restart through the launcher to repair it.";return;}
    }
    // Process lifetime: unloading an interceptor can leave driver callbacks dangling.
    static HMODULE mod{};
    mod=LoadLibraryExW(dll.c_str(),nullptr,LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR|LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
    s.nvidia_fg_mod_status=mod ?
        "Mod preloaded before Streamline. Vulkan FG remains experimental; actual support is checked by the runtime." :
        "Mod could not be loaded. Original NVIDIA path retained; see the launch log.";
    std::printf("DLSSG mod: %ls, loaded=%d, Win32=%lu\n",dll.c_str(),int(mod!=nullptr),mod ? 0ul : GetLastError());
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
               sl::PreferenceFlags::eUseFrameBasedResourceTagging|
               sl::PreferenceFlags::eAllowOTA|sl::PreferenceFlags::eLoadDownloadedPlugins;
    pref.renderAPI=sl::RenderAPI::eVulkan;pref.engineVersion="bbport-TatsunaKyo";
    pref.projectId="42359704-c9f3-4806-9fb5-d469000fdb8a";pref.logMessageCallback=Log;
    const auto result=init(pref,sl::kSDKVersion);
    const auto proc=reinterpret_cast<PFN_vkGetInstanceProcAddr>(GetProcAddress(module,"vkGetInstanceProcAddr"));
    if (result!=sl::Result::eOk || !proc) {
        std::printf("NVIDIA Streamline init failed (%u); native Vulkan retained.\n",unsigned(result));
        if (result==sl::Result::eOk) shutdown_api();return native;
    }
    initialized=true;std::puts("NVIDIA Streamline 2.14.1: Vulkan manual hooks initialized; NVIDIA OTA updates and updated plugin loading enabled.");return reinterpret_cast<void*>(proc);
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
    preset_observer.Start(UpdateTelemetry, [] {
        if (nvapi_unload) nvapi_unload();
        if (nvapi_module) FreeLibrary(nvapi_module);
        nvapi_unload=nullptr;nvapi_module=nullptr;get_override=nullptr;nvapi_attempted=false;
    },std::chrono::milliseconds(100));
}
void BeginRender() {
    if (!initialized || !reflex_supported || !Wanted()) return;
    std::unique_lock lock{mutex};
    BeginRenderLocked(lock);
}
void QueueFlip(int index,int64_t argument) {
    if (!initialized || !reflex_supported || !Wanted()) return;
    std::unique_lock lock{mutex};
    // Starting the render and assigning its flip must use one simulation token.
    // The next simulation is reserved before releasing the guest submission lock.
    if (BeginRenderLocked(lock)) flips.push_back({index,argument,simulation_token});
}
void CancelFlip(int index,int64_t argument) {
    if (!initialized) return;std::scoped_lock lock{mutex};
    std::erase_if(flips,[&](const Flip& f){return f.index==index && f.argument==argument;});
}
void PrepareNextSimulation() {
    if (!initialized || !reflex_supported) return;
    std::scoped_lock lock{mutex};
    if (initialized) simulation_pending=true;
}
bool PacesFrames(unsigned real_limit) {
    if (!initialized || !reflex_supported || !real_limit) return false;
    const auto& s=BbSettings::Get();
    const auto policy=pacing_policy.load();
    return s.frame_generation==BbSettings::FrameGenerationNvidia &&
        s.variable_frame_time && (s.window_focused || s.background_mode==BbSettings::BackgroundRun) &&
        unsigned(policy>>32)==real_limit && unsigned(policy)==unsigned(s.frame_generation_cap_multiplier.load()) &&
        unsigned(policy)>1 && !s.nvidia_api_error;
}
void NextSimulation() {
    if (!initialized || !reflex_supported) return;
    Token next;
    uint64_t requested_policy{};
    sl::ReflexOptions sleep_options;
    {
        std::unique_lock lock{mutex};
        simulation_ready.wait(lock, [] { return !simulation_sleeping || !initialized; });
        if (!initialized) return;
        // Cover token-pool pressure as well as the SDK sleep: allocation can
        // release this mutex while the prior frame still owns its ring slot.
        simulation_sleeping=true;simulation_pending=false;
        const auto ready=[&] { simulation_sleeping=false;simulation_ready.notify_all(); };
        sl::ReflexOptions options;
        const auto& s=BbSettings::Get();
        const bool low_latency=Wanted() && (s.reflex!=0 || s.frame_generation==BbSettings::FrameGenerationNvidia);
        options.mode=low_latency ? s.reflex==2 ? sl::ReflexMode::eLowLatencyWithBoost : sl::ReflexMode::eLowLatency : sl::ReflexMode::eOff;
        // Reflex's interval counts output frames with DLSS FG. Translate the
        // effective real cap (including the optional output cap) to output FPS.
        // At 60 real FPS with x2 this is 120, never a 60 FPS output ceiling.
        const bool driver_pacing=low_latency && fg_on && s.variable_frame_time &&
            s.frame_generation==BbSettings::FrameGenerationNvidia;
        const unsigned real_limit=driver_pacing ?
            BbSettings::EffectiveFrameLimit(EmulatorSettings.GetFrameLimit()) : 0;
        const unsigned multiplier=driver_pacing ? configured_generated+1 : 0;
        const uint64_t output_limit=uint64_t(real_limit)*multiplier;
        options.frameLimitUs=output_limit ? uint32_t((1'000'000+output_limit-1)/output_limit) : 0;
        if (!ApplyReflexOptions(options)) {
            pacing_policy=0;simulation_token.reset();rendering=false;ready();return;
        }
        requested_policy=output_limit ? (uint64_t(real_limit)<<32)|multiplier : 0;
        sleep_options=options;
        if (!Wanted()) {simulation_token.reset();rendering=false;BbSettings::Get().pc_latency_ms=-1.0f;ready();return;}
        next=NewSimulationToken(lock);
        if (!next) {
            pacing_policy=0;
            options.frameLimitUs=0;ApplyReflexOptions(options);
            simulation_token.reset();rendering=false;
            ready();
            return;
        }
        simulation_token=next;rendering=false;
    }
    // Never sleep on Liverpool's EOP thread or while holding m_submit_lock.
    // Previous render submission and present markers must be able to progress.
    const auto sleep_started=BbHitch::Clock::now();
    const auto sleep_result=sleep_api(*static_cast<sl::FrameToken*>(next->native));
    BbHitch::Record("Reflex sleep",sleep_started);
    std::scoped_lock lock{mutex};
    simulation_sleeping=false;simulation_ready.notify_all();
    if (!initialized) {simulation_token.reset();return;}
    if (!Wanted()) {sl::ReflexOptions options;options.mode=sl::ReflexMode::eOff;ApplyReflexOptions(options);pacing_policy=0;simulation_token.reset();rendering=false;return;}
    // Focus/swapchain changes may remove the interval while Sleep is unlocked.
    // Publish ownership only after a successful sleep with that policy intact.
    const bool same_options=reflex_options_applied &&
        applied_reflex_options.mode==sleep_options.mode &&
        applied_reflex_options.frameLimitUs==sleep_options.frameLimitUs;
    pacing_policy=sleep_result==sl::Result::eOk && same_options && fg_on ? requested_policy : 0;
    if (sleep_result!=sl::Result::eOk && same_options) {
        sleep_options.frameLimitUs=0;ApplyReflexOptions(sleep_options);
    }
    Mark(sl::PCLMarker::eSimulationStart,next);
}
void FinishRender(Vulkan::Frame* frame,int index,int64_t argument) {
    std::scoped_lock lock{mutex};
    frame->nvidia_token.reset();
    if (!initialized) return;
    const auto it=std::find_if(flips.begin(),flips.end(),[&](const Flip& f){return f.index==index && f.argument==argument;});
    if (it!=flips.end()) {frame->nvidia_token=std::move(it->token);Mark(sl::PCLMarker::eRenderSubmitEnd,frame->nvidia_token);flips.erase(it);}
}
void RetireFrameToken(Vulkan::Frame* frame) {
    std::scoped_lock lock{mutex};
    frame->nvidia_token.reset();
}
void BeforePresent(Vulkan::Frame* frame,vk::CommandBuffer command,vk::Image image,vk::ImageView view,
                   vk::Format format,uint32_t buffers,bool game_frame,Vulkan::Scheduler& scheduler,
                   uint32_t output_width,uint32_t output_height) {
    if (!initialized) return;std::scoped_lock lock{mutex};
    if (!initialized) return;
    auto& s=BbSettings::Get();const auto lease=frame->nvidia_token;
    auto* token=lease ? static_cast<sl::FrameToken*>(lease->native) : nullptr;
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
        Mark(sl::PCLMarker::ePresentStart,lease);return;
    }
    if (s.frame_generation!=BbSettings::FrameGenerationNvidia) {Mark(sl::PCLMarker::ePresentStart,lease);return;}
    const auto& source=snapshot->source;
    if (source.projection[0]==0 || source.projection[1]==0 || source.projection[3]==0) {
        s.frame_generation_problem="NVIDIA FG is waiting for a valid scene camera.";
        Off();Mark(sl::PCLMarker::ePresentStart,lease);return;
    }
    const uint32_t generated=uint32_t(std::clamp(s.nvidia_generated_frames.load(),1,
        std::max(1,s.nvidia_max_generated.load())));
    if (fg_on && (configured_generated!=generated || configured_width!=snapshot->width ||
        configured_height!=snapshot->height || configured_format!=uint32_t(format))) Off();
    sl::DLSSGOptions options;options.mode=sl::DLSSGMode::eOn;options.numFramesToGenerate=generated;
    // NVIDIA's comparison mode shows interpolated frames without changing inputs.
    const char* generated_only=std::getenv("BB_FG_GENERATED_ONLY");
    if (generated_only && generated_only[0]=='1')
        options.flags|=sl::DLSSGFlags::eShowOnlyInterpolatedFrame;
    options.numBackBuffers=buffers;options.mvecDepthWidth=source.render_width;options.mvecDepthHeight=source.render_height;
    options.colorWidth=snapshot->width;options.colorHeight=snapshot->height;options.colorBufferFormat=uint32_t(format);
    options.mvecBufferFormat=VK_FORMAT_R16G16_SFLOAT;options.depthBufferFormat=VK_FORMAT_R32_SFLOAT;
    // Scene snapshots are immutable until WaitForInputs retires their SDK fence.
    // Avoid inserting FG's completion into the shared rendering/present queue.
    // Bootstrap with automatic queue ordering until SL exposes its input fence.
    options.queueParallelismMode=latest_fence && latest_value ?
        sl::DLSSGQueueParallelismMode::eBlockNoClientQueues :
        sl::DLSSGQueueParallelismMode::eBlockPresentingClientQueue;
    options.onErrorCallback=Error;
    sl::Constants c;
    const auto p=Projection(source.projection),ip=Projection(source.projection,true);
    const auto pp=Projection(source.previous_projection),ipp=Projection(source.previous_projection,true);
    Transpose(c.cameraViewToClip,p);Transpose(c.clipToCameraView,ip);
    Transpose(c.clipToPrevClip,Multiply(Multiply(Multiply(pp,View(source.previous_view)),View(source.inverse_view)),ip));
    Transpose(c.prevClipToClip,Multiply(Multiply(Multiply(p,View(source.view)),View(source.previous_inverse_view)),ipp));
    c.jitterOffset={source.jitter[0],source.jitter[1]};c.mvecScale={1.0f/source.render_width,1.0f/source.render_height};
    c.cameraPinholeOffset={0.0f,0.0f};c.motionVectorsJittered=sl::eFalse;
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
    const sl::Extent render_extent{0,0,source.render_width,source.render_height};
    const sl::Extent output_extent{0,0,snapshot->width,snapshot->height};
    sl::ResourceTag inputs[]={
        {&depth,sl::kBufferTypeDepth,sl::ResourceLifecycle::eValidUntilPresent,&render_extent},
        {&motion,sl::kBufferTypeMotionVectors,sl::ResourceLifecycle::eValidUntilPresent,&render_extent},
        {&color,sl::kBufferTypeBackbuffer,sl::ResourceLifecycle::eValidUntilPresent,&output_extent}};
    const auto options_result=fg_options(viewport,options);
    const auto constants_result=constants(c,*token,viewport);
    const auto tags_result=tags(*token,viewport,inputs,3,reinterpret_cast<sl::CommandBuffer*>(VkCommandBuffer(command)));
    if (options_result!=sl::Result::eOk || constants_result!=sl::Result::eOk || tags_result!=sl::Result::eOk) {
        std::printf("NVIDIA FG: options=%u, constants=%u, tags=%u\n",unsigned(options_result),unsigned(constants_result),unsigned(tags_result));
        fg_on=options_result==sl::Result::eOk;
        Off();failed=true;s.frame_generation_problem="NVIDIA FG input/options failed. Real frames are kept; see last_run.log.";
    } else {
        BbCapture::FrameGenerationCamera diagnostic_camera;
        std::memcpy(diagnostic_camera.view_to_clip.data(),&c.cameraViewToClip,64);
        std::memcpy(diagnostic_camera.clip_to_view.data(),&c.clipToCameraView,64);
        std::memcpy(diagnostic_camera.clip_to_previous.data(),&c.clipToPrevClip,64);
        std::memcpy(diagnostic_camera.previous_to_clip.data(),&c.prevClipToClip,64);
        diagnostic_camera.motion_scale={c.mvecScale.x,c.mvecScale.y};
        diagnostic_camera.reset=c.reset==sl::eTrue;
        Vulkan::FrameGeneration::CaptureDiagnostic(scheduler,device,snapshot->depth.allocator,
            command,*snapshot,image,format,output_width,output_height,uint32_t(*token),generated,
            diagnostic_camera);
        if (!fg_on) frame_metrics.Reset();
        fg_on=true;input_queues_parallel=options.queueParallelismMode==sl::DLSSGQueueParallelismMode::eBlockNoClientQueues;
        s.frame_generation_problem=nullptr;
        s.frame_generation_cap_multiplier=int(generated+1);
        configured_generated=generated;configured_width=snapshot->width;
        configured_height=snapshot->height;configured_format=uint32_t(format);
    }
    Mark(sl::PCLMarker::ePresentStart,lease);
}
bool Present(Vulkan::Frame* frame,const std::function<bool()>& present) {
    if (!initialized) return present();
    // Serialize QueuePresent with GetState, SetOptions, focus and window changes.
    std::scoped_lock lock{mutex};
    if (!initialized) return present();
    const bool presented=present();
    Mark(sl::PCLMarker::ePresentEnd,frame->nvidia_token);
    if (fg_state && fg_on) {
        sl::DLSSGState state;
        const auto result=fg_state(viewport,state,nullptr);
        const bool owned=state.inputsProcessingCompletionFence &&
                         state.lastPresentInputsProcessingCompletionFenceValue;
        if (result==sl::Result::eOk && (!input_queues_parallel || owned)) {
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
            const auto idle=[&] {
                // DeviceWaitIdle requires exclusion of client queue operations.
                // Normal SDK telemetry no longer holds the presentation queue lock.
                std::scoped_lock queue_lock{Vulkan::Scheduler::submit_mutex};
                return device.waitIdle();
            }();
            std::printf("NVIDIA FG ownership unavailable: GetState=%u, fence=%d, GPU drain=%d\n",
                        unsigned(result),int(owned),int(idle));
            ++input_epoch;latest_fence=nullptr;latest_value=0;
            Off();failed=true;
            BbSettings::Get().frame_generation_problem="NVIDIA FG ownership query failed. Real frames are kept; see last_run.log.";
        }
    }
    return presented;
}
void WaitForInputs(Vulkan::Frame* frame) {
    BbHitch::Scope hitch{"FG input retirement"};
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
    token_pool.Notify();simulation_ready.notify_all();
    // Release latency scheduling before the background gate parks GPU workers.
    // NextSimulation rechecks focus after any sleep already in progress.
    if (!Wanted() && reflex_supported && reflex_options) {
        sl::ReflexOptions options;options.mode=sl::ReflexMode::eOff;
        ApplyReflexOptions(options);
    }
}
void Shutdown() {
    if (!initialized) return;BeforeSwapchainChange();std::unique_lock lock{mutex};
    if (!initialized) return;
    if (reflex_options && reflex_supported) {
        sl::ReflexOptions options;options.mode=sl::ReflexMode::eOff;ApplyReflexOptions(options);
    }
    initialized=false;
    token_pool.Notify();simulation_ready.notify_all();
    // Reflex sleeps without this mutex. Let it return before unloading SDK state.
    simulation_ready.wait(lock, [] { return !simulation_sleeping; });
    preset_observer.Stop();
    shutdown_api();simulation_token.reset();flips.clear();device=nullptr;
    BbSettings::Get().nvidia_fg_reported_preset=-1;
    BbSettings::Get().nvidia_fg_preset_status=0;
    simulation_pending=false;pacing_policy=0;reflex_options_applied=false;
    token_pool.Notify();simulation_ready.notify_all();
}
}
#else
namespace BbNvidia {
void PreloadMod() {}
void* VulkanLoader(void* native) {return native;}
void BindDevice(vk::PhysicalDevice,vk::Device) {}
void Shutdown() {}
void BeginRender() {}
void QueueFlip(int,int64_t) {}
void CancelFlip(int,int64_t) {}
void PrepareNextSimulation() {}
void NextSimulation() {}
bool PacesFrames(unsigned) { return false; }
void FinishRender(Vulkan::Frame*,int,int64_t) {}
void RetireFrameToken(Vulkan::Frame* frame) { frame->nvidia_token.reset(); }
void BeforePresent(Vulkan::Frame*,vk::CommandBuffer,vk::Image,vk::ImageView,vk::Format,uint32_t,bool,
                   Vulkan::Scheduler&,uint32_t,uint32_t) {}
bool Present(Vulkan::Frame*,const std::function<bool()>& present) {return present();}
void WaitForInputs(Vulkan::Frame*) {}
void BeforeSwapchainChange() {}
}
#endif
