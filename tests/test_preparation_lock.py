# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Pause the actual preparation branch inside a guest read and publish a shader.

The R42 control blocks publication behind the speculative guest read. Current
code releases the registry, then safely rechecks a grown module list.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
PATH='gpu/shadps4/video_core/renderer_vulkan/vk_pipeline_cache.cpp'
BASE='2fe3a67fc3c2930352bb88af57f881b9b0829494'
PREFIX=r'''
#include <atomic>
#include <cassert>
#include <cstdio>
#include <latch>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <setjmp.h>
#include <shared_mutex>
#include <thread>
#include <tuple>
#include <vector>
#include <algorithm>
using u64=unsigned long long;
std::latch reading(1),resume_read(1);
thread_local sigjmp_buf* runtime_fault_recover{};
namespace Shader {
struct Info {
    unsigned pgm_base{},user_data{};std::vector<unsigned> flattened_ud_buf;
    void RefreshFlatBuf(){if(user_data==99)siglongjmp(*runtime_fault_recover,1);reading.count_down();resume_read.wait();flattened_ud_buf={user_data};}
    void AddBindings(unsigned& b){++b;}
};
struct StageSpecialization {
    int value{};std::optional<unsigned> fetch_shader_data{17};
    StageSpecialization()=default;
    StageSpecialization(Info& i,int,int,unsigned):value(int(i.user_data)){}
    bool operator==(const StageSpecialization& r)const{return value==r.value;}
};
}
struct Program {
    std::unique_ptr<Shader::Info> info_template=std::make_unique<Shader::Info>();
    struct Module{int module{};Shader::StageSpecialization spec;};std::vector<Module> modules;
};
struct Worker {
    bool failed{};std::map<const Program*,Shader::Info> infos;
    struct Stage{const Program* p;u64 hash;unsigned hw,base;std::vector<unsigned>* flat;};
    std::vector<Stage> stages;
};
struct Selection{Worker* worker;};
struct Parameters{u64 hash{1};unsigned user_data{7};unsigned Base()const{return 42;}};
std::shared_mutex programs_mutex;
std::map<u64,std::unique_ptr<Program>> program_cache;
u64 HashCombine(u64 h,size_t p){return h*10000+p;}
using Result=std::tuple<Shader::Info*,int,std::optional<unsigned>,u64>;
Result Prepare(Selection& sel,const Parameters& params,unsigned& binding){
    int runtime_info=0,profile=0;unsigned hw_stage=0;
@BRANCH@
    return {};
}
int main(){
    auto p=std::make_unique<Program>();Shader::StageSpecialization spec;spec.value=7;p->modules.push_back({11,spec});
    auto* original=p.get();program_cache.emplace(1,std::move(p));
    Worker worker;Selection selection{&worker};Parameters params;unsigned binding=0;Result result;
    std::jthread background([&]{result=Prepare(selection,params,binding);});
    reading.wait();const bool can_publish=programs_mutex.try_lock();
#if CONTROL
    assert(!can_publish);std::puts("R42 CONTROL: speculative guest read holds the shader registry; GPU publication is blocked until the read returns.");
#else
    assert(can_publish);
    for(unsigned i=0;i<4096;++i)original->modules.push_back({int(i+100),spec});
    // Force map rehash/tree changes and module-vector reallocation while the
    // guest read is paused. Program objects and worker-owned Info stay alive.
    for(unsigned i=2;i<128;++i)program_cache.emplace(i,std::make_unique<Program>());
    programs_mutex.unlock();
#endif
    resume_read.count_down();background.join();
    assert(!worker.failed && std::get<1>(result)==11 && std::get<3>(result)==10000);
    assert(worker.stages.size()==1 && worker.stages[0].p==original && binding==1);
    assert(worker.stages[0].flat->at(0)==7 && runtime_fault_recover==nullptr);
#if !CONTROL
    // Speculation yields at a busy registry instead of adding another waiter.
    Worker rejected;Selection busy{&rejected};programs_mutex.lock();
    std::jthread contender([&]{unsigned b=0;Prepare(busy,params,b);});contender.join();programs_mutex.unlock();
    assert(rejected.failed && rejected.stages.empty());
    Worker faulted;Selection fault_selection{&faulted};params.user_data=99;
    Prepare(fault_selection,params,binding);
    assert(faulted.failed && faulted.stages.empty() && runtime_fault_recover==nullptr);
    std::puts("PASS: GPU publication completes while the actual worker guest read is paused; current modules are rechecked after reallocation; busy-registry speculation yields.");
#endif
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix='prep-lock-') as temporary:
        folder=Path(temporary)
        for name,control in [('r42',True),('current',False)]:
            text=(subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT,text=True)
                  if control else (ROOT/PATH).read_text())
            start=text.index('    if (sel.worker) {',text.index('PipelineCache::GetProgram('))
            branch=text[start:text.index('\n    auto it_pgm =',start)]
            source=folder/(name+'.cpp');binary=folder/name;source.write_text(PREFIX.replace('@BRANCH@',branch))
            subprocess.run(['g++','-std=c++20','-O1','-UNDEBUG','-pthread','-DCONTROL='+str(int(control)),str(source),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True,timeout=15)


if __name__=='__main__':main()
