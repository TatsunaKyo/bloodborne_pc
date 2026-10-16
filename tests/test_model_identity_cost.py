"""Validate compact model hashing and measure the production old/new identity paths."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE='7f77043936e7e664b57716bc927f424aca96d520'
HEADER='gpu/shadps4/video_core/renderer_vulkan/motion_history.h'
old=subprocess.check_output(['git','show',BASE+':'+HEADER],cwd=ROOT,text=True)
start=old.index('inline std::optional<uint64_t> ModelBatchIdentity(')
finish=old.index('// Keep range scans cached',start)
old=old[start:finish].replace('ModelBatchIdentity(', 'OldModelBatchIdentity(')
HARNESS=r'''
#include <cassert>
#include <chrono>
#include <cstdio>
#include <bit>
#define XXH_INLINE_ALL
#include "xxhash.h"
#include "gpu/shadps4/video_core/renderer_vulkan/motion_history.h"
namespace Vulkan::Motion { __OLD__ }
using namespace Vulkan::Motion;
volatile uint64_t sink;
auto Fast(std::span<const std::byte> data){return ModelBatchIdentity(data,[](auto b){return XXH3_64bits(b.data(),b.size());});}
std::vector<std::byte> Models(size_t count){
 std::vector<std::byte> bytes(count*416);
 for(size_t i=0;i<count;++i)for(size_t j=0;j<12;++j){float value=float(i*12+j+1);std::memcpy(bytes.data()+i*416+j*4,&value,4);}
 return bytes;
}
template<class F>double Time(std::span<const std::byte> data,F fn){
 const auto begin=std::chrono::steady_clock::now();
 for(unsigned i=0;i<40000;++i){asm volatile(""::"g"(data.data()):"memory");sink=*fn(data);}
 return std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-begin).count();
}
int main(){
 for(size_t count:{1,2,4,8,16,32}){
  auto bytes=Models(count);const auto first=Fast(bytes);assert(first);
  assert(ModelBatchIdentity(bytes)==OldModelBatchIdentity(bytes));
  auto camera=bytes;camera[52]^=std::byte{1};assert(Fast(camera)==first);
  for(size_t i=0;i<count;++i)for(size_t component=0;component<12;++component){
   auto changed=bytes;float value=-100.f-float(i+component);
   std::memcpy(changed.data()+i*416+component*4,&value,4);assert(Fast(changed)!=first);
  }
  if(count>1){auto reordered=bytes;std::swap_ranges(reordered.begin(),reordered.begin()+416,reordered.begin()+416);assert(Fast(reordered)!=first);}
  auto invalid=bytes;const float nan=std::bit_cast<float>(uint32_t(0x7fc00000));std::memcpy(invalid.data(),&nan,4);
  assert(!Fast(invalid) && !ModelBatchIdentity(invalid));
  const auto zero=ModelBatchIdentity(bytes,[](auto){return uint64_t(0);});assert(zero && *zero==1);
 }
 assert(!Fast({}) && !Fast(Models(3)) && !Fast(Models(64)));
 auto bytes=Models(32);
 // Interleave controls; report timing without treating host CPU timing as a game benchmark.
 double old=Time(bytes,OldModelBatchIdentity);double fast=Time(bytes,Fast);
 std::printf("40000 identities, 32 records: R46 %.3f ms; compact XXH3 %.3f ms; ratio %.2fx\n",old,fast,old/fast);
 assert(sink);
 std::puts("PASS: all ordered transform components contribute, camera-only bytes excluded, reordered instances differ, invalid matrices rejected, legacy hash preserved and zero normalized.");
}
'''
with tempfile.TemporaryDirectory(prefix='bb-identity-cost-') as temp:
    root=Path(temp);cpp=root/'test.cpp';cpp.write_text(HARNESS.replace('__OLD__',old));exe=root/'identity'
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-I'+str(ROOT),
        '-I'+str(ROOT/'out/test-headers'),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
