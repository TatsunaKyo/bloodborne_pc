"""Exercise per-native-call release, overlapping waiters and a later same-address epoch."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
fixture=r'''
#include "bbport_page_watch_queue.h"
#include <array>
#include <atomic>
#include <cassert>
#include <cstdio>
#include <vector>
using namespace std::chrono_literals;
std::atomic<bool> holdMarker{true},marker{},heldB{},releaseB{};
std::atomic<unsigned> secondCalls{};
std::atomic<bool> firstReady{},releaseFirst{},secondReady{},releaseSecond{};
constexpr uintptr_t Marker=0xffff0000,A=0x100000,B=0x200000,Later=0x600000;
void Until(const std::atomic<bool>& flag){
 const auto end=std::chrono::steady_clock::now()+2s;
 while(!flag){assert(std::chrono::steady_clock::now()<end);std::this_thread::yield();}
}
void Apply(uintptr_t a,uint64_t,uint32_t){
 if(a==Marker){marker=true;while(holdMarker)std::this_thread::yield();}
 if(a==B){heldB=true;Until(releaseB);}
 if(a==Later){
  if(++secondCalls==1){firstReady=true;Until(releaseFirst);}
  else{secondReady=true;Until(releaseSecond);}
 }
}
int main(){
 {
  BbPageWatch::Queue<> q{Apply};q.Push(Marker,1,2);Until(marker);
  q.Push(A,4096,2,A);q.Push(B,4096,2,B);const auto all=q.Seal();holdMarker=false;Until(heldB);
  std::atomic<bool> completed{};std::thread reader([&]{q.WaitRange(A,4096);completed=true;});
  Until(completed);reader.join();assert(q.Complete()<all && !releaseB);
  std::array<std::atomic<bool>,16> done{};std::vector<std::thread> waiters;
  for(unsigned i=0;i<done.size();++i)waiters.emplace_back([&,i]{q.WaitRange(B+i*16,256);done[i]=true;});
  std::this_thread::sleep_for(15ms);for(auto& d:done)assert(!d);
  releaseB=true;for(auto& t:waiters)t.join();q.Wait();for(auto& d:done)assert(d);
 }
 {
  BbPageWatch::Queue<> q{Apply};q.Push(Later,4096,2,Later);Until(firstReady);
  std::atomic<bool> completed{};std::thread reader([&]{q.WaitRange(Later,4096);completed=true;});
  bool registered=false;const auto end=std::chrono::steady_clock::now()+2s;
  while(!registered){
   assert(std::chrono::steady_clock::now()<end);
   for(auto& slot:BbHitch::Trace::journal){
    if(slot.busy.test_and_set(std::memory_order_acquire))continue;
    const auto event=slot.event;slot.busy.clear(std::memory_order_release);
    registered|=event.stage && std::strcmp(event.stage,"snapshot requires watch")==0 && event.address==Later && event.dependency==1;
   }
  }
  q.Push(Later,4096,2,Later);releaseFirst=true;Until(secondReady);Until(completed);
  reader.join();assert(!releaseSecond);releaseSecond=true;q.Wait();
 }
 puts("PASS: a range retires after its own native installation inside an unfinished batch; 16 overlapping waiters wake; later same-address work does not extend a captured read dependency.");
}
'''
with tempfile.TemporaryDirectory(prefix='page-watch-ranges-') as directory:
 p=Path(directory)/'ranges.cpp';p.write_text(fixture);exe=p.with_suffix('')
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shim'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],env={**os.environ,'BB_HITCH_TRACE':'1'},check=True,timeout=20)
