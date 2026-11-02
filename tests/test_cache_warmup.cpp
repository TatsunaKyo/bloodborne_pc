// SPDX-License-Identifier: GPL-2.0-or-later
#include "common/logging/log.h"
#include "common/serdes.h"
#include "core/emulator_settings.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include <array>
#include <chrono>
#include <functional>
#include <optional>
#include <cassert>
#define BB_SHADER_BUILD "current-test-build"
namespace Serialization {constexpr u32 PipelineKeyVersion=7;}
namespace Shader {struct Profile {u32 gpu=1;bool operator==(const Profile&)const=default;};}
namespace Storage {
enum class BlobType {ShaderProfile,PipelineKey};
struct DataBase {
 std::vector<u8> profile,build;
 std::vector<std::vector<u8>> keys;
 unsigned cleared=0,finished=0,saved=0;
 static DataBase& Instance(){static DataBase db;return db;}
 void Open(){}
 void Clear(){++cleared;keys.clear();}
 void Load(BlobType,const char* name,std::vector<u8>& data){data=std::string_view(name)=="profile"?profile:build;}
 void Save(BlobType,const char* name,std::vector<u8>&& data){++saved;(std::string_view(name)=="profile"?profile:build)=std::move(data);}
 void FinishPreload(){++finished;}
 void ForEachBlob(BlobType,const std::function<void(std::vector<u8>&&)>& f){for(auto key:keys)f(std::move(key));}
};
}
namespace Vulkan {
struct PipelineCache {
 Shader::Profile profile;
 struct Selection {std::array<const int*,6> infos{};std::array<void*,6> modules{};std::optional<int> fetch_shader;} sel;
 struct PreloadJob {bool reject=false;};
 std::vector<PreloadJob>* preload_jobs=nullptr;
 unsigned driver_cache_changes=0,loads=0,built=0;
 bool LoadComputePipeline(Serialization::Archive& ar){return Load(ar);}
 bool LoadGraphicsPipeline(Serialization::Archive& ar){return Load(ar);}
 bool Load(Serialization::Archive& ar){
  assert(!sel.infos[0] && !sel.modules[0] && !sel.fetch_shader);
  ++loads;u32 action=0;Serialization::Reader(ar).Read(action);
  static int stage=1;sel.infos[0]=&stage;sel.modules[0]=&stage;sel.fetch_shader=1;
  if(action==1)throw CacheLoadError("driver rejected shader");
  if(action==2)throw Serialization::ReadError("bad shader metadata");
  if(action==3)return false;
  assert(preload_jobs);preload_jobs->push_back({action==4});return true;
 }
 unsigned BuildPreloaded(std::vector<PreloadJob>& jobs){unsigned failed=0;for(auto j:jobs){++built;failed+=j.reject;}return failed;}
 void WarmUp();
};
#include "production_warmup.inc"
}
std::vector<u8> Key(u32 version,u32 kind,u32 action=0){Serialization::Archive ar;Serialization::Writer w(ar);w.Write(version);w.Write(kind);w.Write(action);return ar.TakeOff();}
std::vector<u8> Profile(u32 gpu){std::vector<u8> bytes(sizeof(Shader::Profile));Shader::Profile profile{gpu};std::memcpy(bytes.data(),&profile,sizeof(profile));return bytes;}
int main(){
 auto& db=Storage::DataBase::Instance();
 for(int mode=0;mode<5;++mode){
  db={};db.keys={Key(7,0)};
  if(mode==1)db.profile={1};
  if(mode>=2)db.profile=Profile(mode==2?9:1);
  const std::string build=mode==4?"another-build":BB_SHADER_BUILD;db.build.assign(build.begin(),build.end());
  Vulkan::PipelineCache cache;cache.WarmUp();
  if(mode==3){assert(db.cleared==0 && cache.loads==1 && cache.built==1 && cache.driver_cache_changes==1);}
  else {assert(db.cleared==1 && db.keys.empty() && db.saved==2 && cache.loads==0);assert(db.profile==Profile(1));assert(std::string(db.build.begin(),db.build.end())==BB_SHADER_BUILD);}
  assert(db.finished==1 && !cache.preload_jobs);
 }
 db={};db.profile=Profile(1);std::string build=BB_SHADER_BUILD;db.build.assign(build.begin(),build.end());
 db.keys={{},{1},Key(6,0),Key(7,0,1),Key(7,1,2),Key(7,0,3),Key(7,0,4),Key(7,0),Key(7,1)};
 Vulkan::PipelineCache cache;cache.WarmUp();
 assert(cache.loads==6 && cache.built==3 && cache.driver_cache_changes==2 && db.finished==1 && !cache.preload_jobs);
 std::puts("PASS: current WarmUp body rejects incompatible/missing profiles and builds, skips malformed/driver-rejected records, resets selection and counts failed parallel jobs without losing later valid pipelines.");
}
