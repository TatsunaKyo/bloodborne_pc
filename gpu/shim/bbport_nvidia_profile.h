// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// Read-only DRS telemetry. Layouts from NVIDIA's MIT NVAPI SDK (see third_party/nvapi).
#pragma once
#ifdef _WIN32
#include <windows.h>
#include <cstdint>
#include <cstddef>
#include <cwchar>
namespace BbNvidia::Preset {
namespace Drs {
using Text=uint16_t[2048];
#pragma pack(push,4)
union Value {uint32_t dword;struct {uint32_t size;uint8_t data[4096];} binary;Text text;uint64_t qword;};
struct Setting {uint32_t version;Text name;uint32_t id,type,location,predefined,valid;Value original,current;};
#pragma pack(pop)
struct Application {uint32_t version,predefined;Text name,friendly,launcher;};
static_assert(sizeof(Setting)==12320 && offsetof(Setting,current)==8220);
static_assert(sizeof(Application)==12296);
using Query=void* (__cdecl*)(uint32_t);
// An inherited global value is a configured preference too. Never write DRS here.
inline int ReadPreset(Query query) {
    using Handle=void*;
    const auto create=reinterpret_cast<int (__cdecl*)(Handle*)>(query(0x0694d52e));
    const auto destroy=reinterpret_cast<int (__cdecl*)(Handle)>(query(0xdad9cff8));
    const auto load=reinterpret_cast<int (__cdecl*)(Handle)>(query(0x375dbd6b));
    const auto find=reinterpret_cast<int (__cdecl*)(Handle,const uint16_t*,Handle*,Application*)>(query(0xeee566b2));
    const auto base=reinterpret_cast<int (__cdecl*)(Handle,Handle*)>(query(0xda8466a0));
    const auto get=reinterpret_cast<int (__cdecl*)(Handle,Handle,uint32_t,Setting*)>(query(0x73bf8338));
    if (!create || !destroy || !load || !find || !base || !get) return -1;
    Handle session{},profile{};
    if (create(&session)!=0 || !session) return -1;
    struct Cleanup {Handle session;decltype(destroy) release;~Cleanup(){release(session);}} cleanup{session,destroy};
    if (load(session)!=0) return -1;
    wchar_t path[32768]{};
    const DWORD length=GetModuleFileNameW(nullptr,path,32768);
    if (!length || length>=32768) return -1;
    Application app{};app.version=uint32_t(sizeof(app))|(1u<<16);
    int result=find(session,reinterpret_cast<const uint16_t*>(path),&profile,&app);
    if (result==-166) {
        const auto name=std::wcsrchr(path,L'\\');
        app={};app.version=uint32_t(sizeof(app))|(1u<<16);
        result=find(session,reinterpret_cast<const uint16_t*>(name ? name+1 : path),&profile,&app);
    }
    if (result==-166) result=base(session,&profile);
    if (result!=0 || !profile) return -1;
    Setting setting{};setting.version=uint32_t(sizeof(setting))|(1u<<16);
    if (get(session,profile,0x10e41df1,&setting)!=0 || setting.type!=0) return -1;
    const auto preset=setting.current.dword;
    return preset>=1 && preset<=3 ? int(preset) : -1;
}
} // namespace Drs
} // namespace BbNvidia::Preset
#endif
