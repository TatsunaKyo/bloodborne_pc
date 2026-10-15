// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_hitch.h"
#include <cassert>
#include <thread>
#include <vector>
int main(){
 BbHitch::FrameGate gate;
 for(int i=0;i<100;++i)assert(!gate.Push(16.6667));
 assert(gate.Push(45.1));assert(!gate.Push(17.3));
 gate.Reset();for(int i=0;i<100;++i)assert(!gate.Push(33.3333));
 assert(gate.Push(70));
 gate.Reset();for(int i=0;i<100;++i)assert(!gate.Push(100));
 assert(gate.Push(180));
 using namespace std::chrono_literals;
 std::vector<std::jthread> threads;
 for(int t=0;t<4;++t)threads.emplace_back([]{
  for(int i=0;i<10000;++i){const auto now=BbHitch::Clock::now();BbHitch::Record("fixture",now-2ms,now);}
 });
 threads.clear();
 for(auto& slot:BbHitch::journal){assert(!slot.busy.test_and_set());assert(slot.event.ms==2.0);slot.busy.clear();}
 std::puts("PASS: bounded concurrent CPU wait journal and cadence-relative hitch gate (60, 30 and 10 FPS).");
}
