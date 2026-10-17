"""Exercise production sparse allocation, residency gaps and arena rebinding."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp').read_text()
methods = source[source.index('const Buffer* BufferCache::GetArena('):source.index('std::pair<const Buffer*, u64> BufferCache::ObtainVertexBuffer(')]
header = (ROOT/'gpu/shadps4/video_core/buffer_cache/buffer_cache.h').read_text()
backing = header[header.index('    struct Backing :'):header.index('    IntervalList<Backing>')]
HARNESS = r'''
#include "video_core/buffer_cache/sparse_memory_pool.h"
#include "common/interval_set.h"
#include <deque>
#include <iostream>
#include <memory>
#include <unordered_map>
namespace boost::container {template<class T,size_t>using small_vector=std::vector<T>;}
#define ASSERT_MSG(value, ...) assert(value)
#define LOG_WARNING(...) ((void)0)
#define LOG_INFO(...) ((void)0)
VULKAN_HPP_DEFAULT_DISPATCH_LOADER_DYNAMIC_STORAGE
constexpr u64 MiB=1024*1024;
struct Allocation{u64 bytes;u32 type;};
std::map<VkDeviceMemory,Allocation> physical;
u32 reject_type=~u32{};
u64 serial{},calls{},frees{};u64 reject_above=~u64{},reject_count{};
VKAPI_ATTR VkResult VKAPI_CALL Allocate(VkDevice,const VkMemoryAllocateInfo* info,
 const VkAllocationCallbacks*,VkDeviceMemory* out){
 ++calls;assert(info->allocationSize>0);
#ifndef BB_R45_CONTROL
 const auto* flags=static_cast<const VkMemoryAllocateFlagsInfo*>(info->pNext);
 assert(flags && flags->sType==VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO && (flags->flags&VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT));
#endif
 if(info->memoryTypeIndex==reject_type)return VK_ERROR_OUT_OF_DEVICE_MEMORY;
 if(info->allocationSize>reject_above || reject_count){if(reject_count)--reject_count;return VK_ERROR_OUT_OF_DEVICE_MEMORY;}
 *out=reinterpret_cast<VkDeviceMemory>(++serial);
 assert(physical.emplace(*out,Allocation{info->allocationSize,info->memoryTypeIndex}).second);
 return VK_SUCCESS;
}
VKAPI_ATTR void VKAPI_CALL Free(VkDevice,VkDeviceMemory memory,const VkAllocationCallbacks*){
 assert(physical.erase(memory)==1);++frees;
}
namespace Common {template<class T>T AlignDownPow2(T n,T align){return n&~(align-1);}}
namespace BbStats {inline int t_resident;struct Timer{explicit Timer(int){}};}
namespace Vulkan {template<class T>T Check(vk::ResultValue<T> v){assert(v.result==vk::Result::eSuccess);return v.value;}}
namespace VideoCore {
enum class MemoryType{Sparse,HostUncached};
struct Instance{vk::Device GetDevice()const{return vk::Device(reinterpret_cast<VkDevice>(1));}};
struct Buffer{
 u64 cpu_addr{},size_bytes{},id{};
 Buffer()=default;
 Buffer(Instance,u64 base,u64 size,MemoryType):cpu_addr(base),size_bytes(size),id(++ids){}
 static inline u64 ids{};
 u64 BufferDeviceAddress()const{return id<<40;}
};
struct StagingPool{
 struct Staging{u8* mapped;u64 offset;const Buffer* buffer;void Flush()const{}};
 std::deque<std::vector<u64>> data;Buffer buffer;
 Staging Request(u64 bytes,MemoryType){data.emplace_back((bytes+7)/8);return {reinterpret_cast<u8*>(data.back().data()),0,&buffer};}
};
struct Runtime{
 StagingPool* staging;std::map<u64,u64> addresses;
 void CopyBuffer(const Buffer*,const Buffer*,const auto& copies){
  const auto& data=staging->data.back();
  for(auto copy:copies)for(u64 i=0;i<copy.size;i+=8)addresses[(copy.dstOffset+i)/8]=data[(copy.srcOffset+i)/8];
 }
};
class BufferCache{
public:
 __BACKING__
 struct ArenaBinds{const Buffer* arena;std::vector<vk::SparseMemoryBind> binds;};
 Instance instance{};u32 block_shift=16,block_size=1<<16,arena_memory_type_index=3;
 u64 arena_page_bits=24,arena_page_size=1<<24,blocks_per_arena_page=256,blocks_per_arena_page_shift=8;
 SparseMemoryPool backing_pool;std::deque<Buffer> arenas;
 std::array<const Buffer*,64> address_space{};std::deque<ArenaBinds> pending_binds;
 IntervalList<Backing> resident_ranges;
 StagingPool staging_pool;Runtime runtime{&staging_pool};
 std::unique_ptr<Buffer> bda_pagetable_buffer=std::make_unique<Buffer>();
 ArenaBinds* BindsForArena(const Buffer* arena){for(auto& b:pending_binds)if(b.arena==arena)return &b;return &pending_binds.emplace_back(arena);}
 BufferCache(){backing_pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,block_size,1ull<<32,8ull<<30);}
 const Buffer* GetArena(u64,u64);
 void EnsureResident(const Buffer*,u64,u64);
 void Obtain(u64 first,u64 last){const auto* arena=GetArena(first,last);EnsureResident(arena,first,last);}
};
__METHODS__
}
using VideoCore::SparseMemoryPool;
void Reset(){assert(physical.empty());calls=frees=serial=0;reject_above=~u64{};reject_count=0;}
void Bounds(SparseMemoryPool::Slice s,u64 bytes,u64 align){
 assert(s.offset%align==0);auto a=physical.at(VkDeviceMemory(s.memory));
 assert(s.offset+bytes<=a.bytes && a.type==3);
}
int main(){
 VULKAN_HPP_DEFAULT_DISPATCHER.vkAllocateMemory=Allocate;
 VULKAN_HPP_DEFAULT_DISPATCHER.vkFreeMemory=Free;
#ifdef BB_R45_CONTROL
 {VideoCore::BufferCache cache;for(u64 i=0;i<261;++i)cache.Obtain(i,i);assert(calls==261);}
 std::cout<<"R45 production control: 261 x 64 KiB new bindings: "<<calls<<" driver allocations\n";
 while(!physical.empty())Free({},physical.begin()->first,nullptr);
 return 0;
#endif
 {SparseMemoryPool pool;reject_type=3;pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,65536,1ull<<32,8ull<<30,{7});
  auto result=pool.Allocate(65536);assert(result.result==vk::Result::eSuccess && physical.begin()->second.type==7);}
 reject_type=~u32{};Reset();
 for(u64 alignment:{16ull*1024,64ull*1024,256ull*1024}){
  Reset();{
   SparseMemoryPool pool;pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,alignment,1ull<<32,8ull<<30);
   std::map<VkDeviceMemory,std::vector<std::pair<u64,u64>>> used;
   for(unsigned i=0;i<261;++i){auto r=pool.Allocate(alignment);assert(r.result==vk::Result::eSuccess);Bounds(r.value,alignment,alignment);
    auto& ranges=used[VkDeviceMemory(r.value.memory)];for(auto [a,b]:ranges)assert(r.value.offset+alignment<=a || r.value.offset>=b);
    ranges.emplace_back(r.value.offset,r.value.offset+alignment);
   }
   const u64 expected=(261*alignment+16*MiB-1)/(16*MiB);assert(calls==expected);
   if(alignment==64*1024)std::cout<<"261 x 64 KiB new bindings: "<<calls<<" driver allocations (previously 261)\n";
  }assert(frees==calls && physical.empty());
 }
 Reset();{
  SparseMemoryPool pool;pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,65536,1ull<<32,8ull<<30);
  auto a=pool.Allocate(65536);auto b=pool.Allocate(32*MiB);auto c=pool.Allocate(65536);
  assert(calls==2 && a.value.memory==c.value.memory && a.value.memory!=b.value.memory);
  assert(c.value.offset==65536);Bounds(b.value,32*MiB,65536);
 }
 Reset();{
  SparseMemoryPool pool;pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,16384,MiB,64*MiB);
  auto a=pool.Allocate(16384);Bounds(a.value,16384,16384);assert(physical.begin()->second.bytes==256*1024);
 }
 Reset();reject_above=65536;{
  SparseMemoryPool pool;pool.Initialize(vk::Device(reinterpret_cast<VkDevice>(1)),3,65536,1ull<<32,8ull<<30);
  auto a=pool.Allocate(65536);assert(a.result==vk::Result::eSuccess && calls==2);Bounds(a.value,65536,65536);
  reject_count=2;auto fail=pool.Allocate(65536);assert(fail.result==vk::Result::eErrorOutOfDeviceMemory && !fail.value.memory);
  auto again=pool.Allocate(65536);assert(again.result==vk::Result::eSuccess);Bounds(again.value,65536,65536);
 }assert(frees==2 && physical.empty());
 Reset();{
  VideoCore::BufferCache cache;
  for(u64 i=0;i<261;++i)cache.Obtain(i,i);
  assert(calls==2 && cache.resident_ranges.Size()==2);
  // A binding spanning the 16 MiB arena boundary rebinds already-live storage.
  cache.Obtain(255,256);auto* merged=cache.address_space[0];assert(merged==cache.address_space[1]);
  const auto* binds=cache.BindsForArena(merged);
  for(const auto& bind:binds->binds){
   u64 block=(bind.resourceOffset+merged->cpu_addr)>>cache.block_shift;
   auto r=cache.resident_ranges.Find(block);assert(r!=cache.resident_ranges.end());
   assert(bind.memory==r->memory);
   assert(bind.memoryOffset==(r->offset+block-r->start)*cache.block_size);
  }
  const auto old=calls;cache.Obtain(0,260);assert(calls==old);
 }
 Reset();{
  VideoCore::BufferCache cache;
  for(u64 i:{0,2,4,9})cache.Obtain(i,i);
  cache.Obtain(0,9);assert(cache.resident_ranges.Contains(0,10) && calls==1);
  std::map<u64,u64> physical_offsets;
  for(const auto& range:cache.resident_ranges){
   auto part=range.SubRange(range.start+1,range.end);assert(part.offset==range.offset+1);
   for(u64 block=range.start;block<range.end;++block){
    const u64 offset=(range.offset+block-range.start)*cache.block_size;
    assert(physical_offsets.emplace(offset,block).second);
    assert(cache.runtime.addresses.contains(block));
   }
  }
  assert(physical_offsets.size()==10);
 }
 assert(physical.empty());
 std::cout<<"PASS: production sparse pool/residency/gaps/coalescing/arena migration, alignment, no aliases, exact-size OOM fallback, failure recovery and destruction.\n";
}
'''
with tempfile.TemporaryDirectory(prefix='bb-sparse-pool-') as temp:
    folder=Path(temp)
    def run(name, body, flags=()):
        cpp=folder/(name+'.cpp')
        cpp.write_text(HARNESS.replace('__BACKING__',backing).replace('__METHODS__',body))
        exe=folder/(name+('.exe' if os.name=='nt' else ''))
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread',*flags,
            '-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),'-I'+str(ROOT/'out/test-headers'),
            str(cpp),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
    baseline=subprocess.check_output(['git','show',
        'c02ab3328ad2204f96849642d4ce8d8c6e72ccd5:gpu/shadps4/video_core/buffer_cache/buffer_cache.cpp'],cwd=ROOT,text=True)
    control=baseline[baseline.index('const Buffer* BufferCache::GetArena('):baseline.index('bool BufferCache::SynchronizeMemory(')]
    run('r45-control',control,('-DBB_R45_CONTROL',))
    run('pool',methods)
