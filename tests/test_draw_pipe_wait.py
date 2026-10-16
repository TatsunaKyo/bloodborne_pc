# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Execute production queue/helper waits, CPU usage, wake races and ring wraps.

The R43 control consumes CPU while another thread deliberately holds its work.
Current code must block without losing wakeups, packet order or copy flushing.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'cbb4acbc71372f20b7291ebe9e50baf8c7e4a3b7'
HEADERS = ('vk_draw_pipe.h', 'vk_bind_helper.h')
PREFIX = 'gpu/shadps4/video_core/renderer_vulkan/'
HARNESS = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <latch>
#include <thread>
#ifdef _WIN32
#include <windows.h>
static unsigned gettid(){return GetCurrentThreadId();}
#else
#include <time.h>
#endif
#include "vk_draw_pipe.h"
#include "vk_bind_helper.h"
namespace BbCopy { void FlushBatch() {} }
using namespace std::chrono_literals;
double CpuMs(){
#ifdef _WIN32
    FILETIME created,exited,kernel,user;
    assert(GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user));
    const auto value=[](FILETIME t){return (std::uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime;};
    return double(value(kernel)+value(user))/10000.0;
#else
    timespec t{};assert(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)==0);
    return double(t.tv_sec)*1000.0+double(t.tv_nsec)/1e6;
#endif
}
struct Held {std::latch entered{1},resume{1};};
void Hold(void* p){auto& h=*static_cast<Held*>(p);h.entered.count_down();h.resume.wait();}
void HoldPacket(void* p,const std::uint8_t*,std::uint32_t){Hold(p);}
template<class F> double WaitCpu(Held& held,F&& wait){
    held.entered.wait();
    std::jthread release([&]{std::this_thread::sleep_for(40ms);held.resume.count_down();});
    const double start=CpuMs();wait();return CpuMs()-start;
}
struct Ordered {std::uint64_t next=0;unsigned payload=8;};
void Packet(void* p,const std::uint8_t* data,std::uint32_t size){
    auto& state=*static_cast<Ordered*>(p);assert(size==state.payload);
    std::uint64_t number;std::memcpy(&number,data,8);assert(number==state.next++);
    if(size>8){std::uint64_t tail;std::memcpy(&tail,data+size-8,8);assert(tail==(number^0xd0c0b0a0));}
    if((number&63)==0)std::this_thread::sleep_for(250us);
}
void Post(Vulkan::DrawPipe& pipe,std::uint64_t value,unsigned size=8){
    auto* data=pipe.Begin(size);std::memcpy(data,&value,8);
    if(size>8){const auto tail=value^0xd0c0b0a0;std::memcpy(data+size-8,&tail,8);}
    pipe.Commit(size);
}
void Increment(void* p){++*static_cast<std::uint64_t*>(p);}
int main(){
    double draw_cpu,helper_cpu;
    {Held held;Vulkan::DrawPipe pipe(HoldPacket,&held);Post(pipe,0);
     draw_cpu=WaitCpu(held,[&]{pipe.Drain();});}
    {Held held;Vulkan::BindHelper helper(true);helper.Fork(Hold,&held);
     helper_cpu=WaitCpu(held,[&]{helper.Join();});}
#if CONTROL
    assert(draw_cpu>5.0 && helper_cpu>5.0);
    std::printf("R43 CONTROL: 40 ms held work consumes %.3f ms producer CPU and %.3f ms helper-wait CPU.\n",draw_cpu,helper_cpu);
#else
    assert(draw_cpu<5.0 && helper_cpu<5.0);
    std::printf("PASS: 40 ms held work consumes %.3f ms producer CPU and %.3f ms helper-wait CPU.\n",draw_cpu,helper_cpu);
#endif
    {Ordered state;state.payload=257*1024;Vulkan::DrawPipe pipe(Packet,&state);
     for(unsigned i=0;i<160;++i)Post(pipe,i,state.payload);
     pipe.Drain();assert(state.next==160 && pipe.Idle());}
    {Ordered state;Vulkan::DrawPipe pipe(Packet,&state);
     for(unsigned i=0;i<6000;++i){Post(pipe,i);pipe.Drain();assert(state.next==i+1);}}
    {std::uint64_t count=0;Vulkan::BindHelper helper(true);
     for(unsigned i=0;i<10000;++i){helper.Fork(Increment,&count);helper.Join();assert(count==i+1);}}
    std::puts("PASS: production ring wraps/backpressure, 6000 drain wake races, 10000 helper handoffs and idle shutdown preserve ordering.");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', default='g++')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='draw-pipe-wait-') as temporary:
        temp = Path(temporary)
        stub = temp / 'stubs/common'
        stub.mkdir(parents=True)
        (stub/'thread.h').write_text('#pragma once\nnamespace Common {inline void SetCurrentThreadName(const char*){}}\n')
        (stub/'types.h').write_text('#pragma once\n#include <cstdint>\nusing u8=std::uint8_t;using u32=std::uint32_t;using u64=std::uint64_t;\n')
        (stub/'assert.h').write_text('#pragma once\n#include <cassert>\n#define ASSERT(x) assert(x)\n')
        for name, control in [('r43', True), ('current', False)]:
            folder = temp/name
            folder.mkdir()
            for filename in HEADERS:
                source = subprocess.check_output(['git','show',BASE+':'+PREFIX+filename],cwd=ROOT,text=True) if control else (ROOT/PREFIX/filename).read_text()
                (folder/filename).write_text(source)
            cpp = folder/'test.cpp'
            cpp.write_text(HARNESS)
            msvc = Path(args.compiler).stem.lower() in ('cl','clang-cl')
            binary = folder/('test.exe' if msvc else 'test')
            includes = [temp/'stubs', folder, ROOT/'gpu/shim']
            if msvc:
                command = [args.compiler,'/nologo','/O2','/EHsc','/std:c++20','/UNDEBUG','/DCONTROL='+str(int(control))]+['/I'+str(p) for p in includes]+[str(cpp),'/Fe:'+str(binary)]
            else:
                command = [args.compiler,'-std=c++20','-O2','-UNDEBUG','-pthread','-DCONTROL='+str(int(control))]+[item for p in includes for item in ('-I',str(p))]+[str(cpp),'-o',str(binary)]
            subprocess.run(command,cwd=folder,check=True)
            subprocess.run([str(binary)],cwd=ROOT,check=True,timeout=60)


if __name__ == '__main__':
    main()
