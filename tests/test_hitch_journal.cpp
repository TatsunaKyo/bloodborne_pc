// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_hitch.h"
#include <cassert>
#include <thread>
#include <vector>
int main(){
 using namespace std::chrono_literals;
 const auto beginning=BbHitch::Clock::time_point{}+1s;
 const auto event=[](const char* stage,auto begin,auto end){return BbHitch::Event{stage,end,BbHitch::SubmissionTracker::Milliseconds(begin,end),begin};};
 const auto old_event=event("old frame",beginning,beginning+20ms);
 assert(BbHitch::Overlap(old_event,beginning+30ms,beginning+50ms)==0);
 const auto crossing=event("crossing",beginning+20ms,beginning+70ms);
 assert(BbHitch::Overlap(crossing,beginning+30ms,beginning+50ms)==20);
 assert(BbHitch::Overlap(crossing,beginning+30ms,beginning+30ms)==0);
 std::array<BbHitch::Event,128> events{};
 events[0]=old_event;events[1]=crossing;
 events[2]=event("inside",beginning+35ms,beginning+45ms);
 events[3]=event("next frame",beginning+50ms,beginning+70ms);
 events[4]=event(crossing.stage,beginning+25ms,beginning+40ms);
 const auto selected=BbHitch::SelectWindow(events,5,beginning+30ms,beginning+50ms);
 assert(selected[0].event==&events[1] && selected[0].overlap==20);
 assert(selected[1].event==&events[2] && selected[1].overlap==10 && !selected[2].event);
 BbHitch::SubmissionTracker submissions;
 const auto first=submissions.Queue(1,0,beginning);
 const auto second=submissions.Queue(1,0,beginning+16ms);
 const auto third=submissions.Queue(2,2,beginning+32ms);
 submissions.Cancel(second);
 const auto first_path=submissions.Take(1,0,beginning+5ms);
 assert(first_path.id==first && first_path.submitted==beginning);
 assert(submissions.Take(1,0,beginning+20ms).id==0);
 const auto third_path=submissions.Take(2,2,beginning+40ms);
 assert(third_path.id==third && third_path.submit_interval==16.0 && third_path.gpu_interval==20.0);
 assert(BbHitch::SubmissionTracker::Milliseconds(third_path.submitted,third_path.gpu_flip)==8.0);
 // A bounded registry must remain usable even with more submissions than slots.
 for(int i=0;i<100;++i)submissions.Queue(i,i,beginning+std::chrono::milliseconds(i+50));
 assert(submissions.Take(0,0,beginning+200ms).id==0);
 assert(submissions.Take(99,99,beginning+200ms).id!=0);
 BbHitch::FrameGate gate;
 for(int i=0;i<100;++i)assert(!gate.Push(16.6667));
 assert(gate.Push(45.1));assert(!gate.Push(17.3));
 gate.Reset();for(int i=0;i<100;++i)assert(!gate.Push(33.3333));
 assert(gate.Push(70));
 gate.Reset();for(int i=0;i<100;++i)assert(!gate.Push(100));
 assert(gate.Push(180));
 std::vector<std::jthread> threads;
 for(int t=0;t<4;++t)threads.emplace_back([]{
  for(int i=0;i<10000;++i){const auto now=BbHitch::Clock::now();BbHitch::Record("fixture",now-2ms,now);}
 });
 threads.clear();
 for(auto& slot:BbHitch::journal){assert(!slot.busy.test_and_set());assert(slot.event.ms==2.0);slot.busy.clear();}
 std::puts("PASS: bounded submission-to-flip chronology, repeated arguments, cancellation and overflow; concurrent CPU wait journal and cadence-relative hitch gate (60, 30 and 10 FPS).");
}
