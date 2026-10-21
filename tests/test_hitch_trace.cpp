// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_hitch.h"
#include <cassert>
#include <cmath>
#include <cstring>
#include <thread>
#include <vector>
using namespace std::chrono_literals;
int main() {
    using namespace BbHitch::Trace;
    const auto begin = Clock::time_point{} + 100ms, end = begin + 50ms;
    std::array<Summary,4> rows{};
    const char* operation = "short resource bind";
    for (int i=0;i<100;++i)
        assert(Accumulate(rows,{operation,"draw recording",begin+i*200us,begin+(i+1)*200us,1},begin,end));
    assert(rows[0].count==100 && std::abs(rows[0].total-20.0)<1e-8);
    assert(std::abs(rows[0].peak-0.2)<1e-8); // R44's 1 ms journal omits every one of these.
    Accumulate(rows,{operation,"Vulkan recording",begin-2ms,begin+3ms,2},begin,end);
    assert(rows[1].thread==2 && rows[1].total==3.0);
    Accumulate(rows,{"nested allocation","draw recording",begin+2ms,begin+7ms,1},begin,end);
    assert(rows[2].total==5.0 && std::abs(rows[0].total-20.0)<1e-8); // Inclusive scopes stay separate.
    Accumulate(rows,{"previous frame","other",begin-10ms,begin,3},begin,end);
    Accumulate(rows,{"next frame","other",end,end+10ms,3},begin,end);
    assert(!rows[3].stage);
    assert(Overlap({operation,"other",begin+2ms,begin,1},begin,end)==0);
    assert(Overlap({operation,"other",begin,end,1},end,begin)==0);
    std::array<Summary,1> bounded{};
    assert(Accumulate(bounded,{operation,"draw",begin,end,1},begin,end));
    assert(!Accumulate(bounded,{"another stage","draw",begin,end,1},begin,end));
    std::array<Summary,4> resources{};
    Accumulate(resources,{operation,"draw",begin-1ms,begin+1ms,7,0x20000,4096},begin,end);
    Accumulate(resources,{operation,"draw",begin+1ms,begin+2ms,7,0x10000,8192},begin,end);
    assert(resources[0].bytes==12288 && resources[0].count==2 && resources[0].total==2.0);
    assert(resources[0].min_address==0x10000 && resources[0].max_address==0x20000);
    const auto tiny_start=Clock::now();
    BbHitch::Record(operation,tiny_start,tiny_start+200us);
    assert(BbHitch::next.load()==0); // Ordinary hitch journal remains unchanged.
    assert(writes.load()==(Enabled()?1u:0u));
    std::vector<std::jthread> workers;
    for(unsigned i=0;i<4;++i)workers.emplace_back([&] {
        SetRole("fixture worker");
        for(unsigned j=0;j<40000;++j)Record(operation,begin,end);
    });
    workers.clear();
    assert(writes.load()==(Enabled()?160001u:0u));
    if(Enabled()) {
        size_t valid=0;
        for(auto& slot:journal)if(slot.event.stage) {
            assert(slot.event.stage==operation && slot.event.thread && slot.event.end>=slot.event.start);
            ++valid;
        }
        assert(valid==Capacity); // Wrap is bounded, even with concurrent producers.
    }
    std::puts("PASS: sub-millisecond attribution, phase clipping, separate threads, nested totals, category bounds, concurrent ring wrap and disabled fast path.");
}
