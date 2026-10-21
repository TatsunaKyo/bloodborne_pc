"""Run production queue/snapshot/publication code against a delayed deterministic driver."""
from pathlib import Path
import subprocess,tempfile,os
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_cache.cpp').read_text()
a=s.index('struct PipelineCache::PendingBuild {');b=s.index('bool PipelineCache::PrepareGraphicsPipeline(',a);production=s[a:b]
template=r'''
#include "common/pipeline_build_queue.h"
#include <array>
#include <optional>
#include <memory>
#include <future>
#include <span>
#include <unordered_map>
#include <unordered_set>
#include <chrono>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <algorithm>
using u32=uint32_t;using u64=uint64_t;constexpr size_t MaxShaderStages=2;
using GraphicsPipelineKey=u64;
namespace Shader {struct Info {std::vector<u32> flattened_ud_buf;std::span<const u32> user_data;};struct RuntimeInfo {int value=0;};namespace Gcn {struct FetchShaderData {int value=0;};}}
namespace vk {using ShaderModule=int;}
struct Instance {bool dynamic=true;bool IsVertexInputDynamicState()const{return dynamic;}};
std::atomic_bool allow_driver{false};std::atomic_int runs=0,fail_key=0;
struct GraphicsPipeline {
 struct SerializationSupport {int value=0;};
 std::array<const Shader::Info*,2> stages{};u32 flat=0,user=0;int runtime=0,fetch=0;bool valid=true;
 GraphicsPipeline(const Instance&,int&,int&,int&,u64 key,int,std::array<const Shader::Info*,2> infos,
  std::array<Shader::RuntimeInfo,2> rt,const Shader::Gcn::FetchShaderData* f,std::array<int,2>,SerializationSupport& support,bool) {
  allow_driver.wait(false);++runs;stages=infos;flat=infos[0]->flattened_ud_buf.at(0);user=infos[0]->user_data.empty()?0:infos[0]->user_data[0];
  runtime=rt[0].value;fetch=f?f->value:0;support.value=123;valid=int(key)!=fail_key.load();
 }
 bool Handle()const{return valid;}
 void UseLiveStages(std::array<const Shader::Info*,2> live){stages=live;}
};
struct PipelineSelection {std::array<const Shader::Info*,2> infos{};std::array<Shader::RuntimeInfo,2> runtime_infos{};std::array<int,2> modules{};std::optional<Shader::Gcn::FetchShaderData> fetch_shader;u64 graphics_key=1;};
unsigned registered=0;void RegisterPipelineData(u64,size_t,GraphicsPipeline::SerializationSupport& s){assert(s.value==123);++registered;}
struct PipelineCache {
 struct PendingBuild;
 std::unique_ptr<Common::PipelineBuildQueue> build_queue=std::make_unique<Common::PipelineBuildQueue>(2);
 std::mutex builds_mutex;std::unordered_map<u64,std::shared_ptr<PendingBuild>> builds;std::unordered_set<u64> published_builds;
 Instance instance;int scheduler=0,desc_heap=0,profile=0;std::optional<int> pipeline_cache=42;
 std::unordered_map<u64,std::unique_ptr<GraphicsPipeline>> graphics_pipelines;PipelineSelection sel;unsigned num_new_pipelines=0;
 void QueueBuild(const PipelineSelection&,const GraphicsPipeline::SerializationSupport* cached=nullptr);
 bool FinishBuild(const GraphicsPipelineKey&,bool);void PublishPreloads();void ReapBuilds();void StopBuilds();
 ~PipelineCache(){StopBuilds();}
};
@PRODUCTION@
int main(){
 PipelineCache cache;Shader::Info info{{11},{}};std::vector<u32> user{22};info.user_data=user;
 cache.sel.infos[0]=&info;cache.sel.runtime_infos[0].value=33;cache.sel.fetch_shader=Shader::Gcn::FetchShaderData{44};
 cache.QueueBuild(cache.sel);cache.QueueBuild(cache.sel);assert(cache.builds.size()==1);
 info.flattened_ud_buf[0]=111;user[0]=222;cache.sel.runtime_infos[0].value=333;cache.sel.fetch_shader->value=444;
 auto pending=std::async(std::launch::async,[&]{return cache.FinishBuild(1,true);});
 assert(pending.wait_for(std::chrono::milliseconds(5))==std::future_status::timeout);
 allow_driver=true;allow_driver.notify_all();assert(pending.get());auto& pipe=*cache.graphics_pipelines.at(1);
 assert(pipe.flat==11 && pipe.user==22 && pipe.runtime==33 && pipe.fetch==44);
 assert(pipe.stages[0]==&info && pipe.stages[0]->flattened_ud_buf[0]==111 && registered==1);
 cache.QueueBuild(cache.sel);assert(cache.builds.empty());
 fail_key=2;cache.sel.graphics_key=2;cache.QueueBuild(cache.sel);assert(!cache.FinishBuild(2,true));assert(!cache.graphics_pipelines.contains(2));
 cache.instance.dynamic=false;cache.sel.graphics_key=3;cache.QueueBuild(cache.sel);assert(cache.builds.empty());
 GraphicsPipeline::SerializationSupport support;cache.QueueBuild(cache.sel,&support);cache.build_queue->Drain();cache.PublishPreloads();assert(cache.graphics_pipelines.contains(3) && registered==1);
 allow_driver=false;cache.instance.dynamic=true;unsigned accepted=0;
 for(unsigned i=10;i<1000;++i){cache.sel.graphics_key=i;cache.QueueBuild(cache.sel);}
 accepted=cache.builds.size();assert(accepted==128);
 allow_driver=true;allow_driver.notify_all();cache.StopBuilds();assert(unsigned(runs.load())>=accepted+3);
 for(auto& [key,job]:cache.builds)job->queued-=std::chrono::seconds(3);
 cache.ReapBuilds();assert(cache.builds.empty());
 std::cout<<"PASS production compile ahead: immutable flat/user/runtime/fetch snapshots, deduplication, strict wait, live rebinding, failure fallback, cached static inputs, 128-job bound, draining stop and stale-job reclamation.\n";
}
'''
with tempfile.TemporaryDirectory(prefix='compile-ahead-') as d:
 d=Path(d);cpp=d/'test.cpp';exe=d/'test';cpp.write_text(template.replace('@PRODUCTION@',production))
 subprocess.run([*os.environ.get('CXX','g++').split(),'-std=c++20','-O1','-pthread','-I'+str(ROOT/'gpu/shadps4'),str(cpp),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=30)
