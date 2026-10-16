"""Execute production direct-index snapshot selection and verify every fetched byte."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp').read_text()
a=source.index('void Rasterizer::PrepareVertexFetch(')
method=source[a:source.index('void Rasterizer::ResolveVertexBuffers(',a)]
fixture=r'''
#include "video_core/buffer_cache/vertex_fetch_range.h"
#include "video_core/renderer_vulkan/motion_history.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <optional>
#include <random>
using u8=uint8_t;using u16=uint16_t;using u32=uint32_t;using s32=int32_t;using u64=uint64_t;using VAddr=uintptr_t;
namespace Motion=Vulkan::Motion;
namespace AmdGpu{enum class IndexType{Index16,Index32};}
namespace Shader{enum class SwStage{Vertex};}
namespace vk{enum class IndexType{eUint16,eUint32};}
struct Fetch{std::vector<unsigned> attributes{0};};
struct GraphicsPipeline{
 std::optional<Fetch> fetch=Fetch{};
 const auto& GetFetchShader()const{return fetch;}
 int GetStage(Shader::SwStage)const{return 0;}
};
struct RegisterAddress{VAddr value{};template<class T>T Address()const{return T(value);}};
struct Registers{
 u32 index_offset{},num_indices{};RegisterAddress index_base_address;
 struct{AmdGpu::IndexType index_type=AmdGpu::IndexType::Index16;}index_buffer_type;
 u32 enable_primitive_restart{},primitive_restart_index=0xffff;
} regs;
std::pair<u32,u32> GetDrawOffsets(const Registers& r,int,const std::optional<Fetch>&){return {r.index_offset,0};}
struct Memory{
 bool safe=true;unsigned copies{};
 bool CanReadAhead(VAddr,u64){return safe;}
 void CopySparseMemory(VAddr a,u8* out,u64 n){++copies;std::memcpy(out,reinterpret_cast<void*>(a),n);}
};
struct Stream{
 std::vector<u8> bound;
 u64 Copy(const void* p,u64 n,u64){bound.assign(static_cast<const u8*>(p),static_cast<const u8*>(p)+n);return 128;}
 int Handle()const{return 1;}
};
namespace VideoCore{struct BufferCache{
 static constexpr u64 STREAM_THRESHOLD=16384;
 bool gpu_written{};Stream stream;
 bool IsRegionGpuModified(VAddr,u64){return gpu_written;}
 Stream& GetStreamBuffer(){return stream;}
};}
struct Rasterizer{
 Memory* memory;VideoCore::BufferCache buffer_cache;
 struct{Vulkan::Motion::VertexRange records{};bool direct{},indices_ready{};VAddr index_address{};std::vector<u8> indices;}vertex_fetch;
 struct{int handle;u64 offset;vk::IndexType type;}index_bind{};
 struct{bool IsBufferAccessed(Stream*,u64,u64){return false;}}runtime;
 bool needs_barrier{};
 const Registers& Regs()const{return regs;}
 void PrepareVertexFetch(const GraphicsPipeline*,bool,u32);
};
@METHOD@
int main(int argc,char**){
 // Include strides, offset attributes, signed base vertices and clipped bounds.
 std::mt19937 random{0x51414};
 for(unsigned n=0;n<30000;++n){
  const u32 bytes=1+random()%200000,stride=random()%128,first=random()%3000,count=1+random()%40;
  const u32 offset=random()%96,width=1+random()%32;
  const auto range=VideoCore::VertexFetch::Bytes(bytes,stride,first,count,u64(offset)+32);
  assert(range.size && u64(range.offset)+range.size<=bytes);
  for(u64 record=first;record<u64(first)+count;++record){
   const u64 begin=record*stride+offset,end=std::min<u64>(bytes,begin+width);
   if(begin<end)assert(range.offset<=begin && u64(range.offset)+range.size>=end);
  }
 }
 Memory memory;Rasterizer r{&memory};GraphicsPipeline pipeline;
 std::vector<u16> indices={55,55,100,107,101,0xffff};
 regs.index_base_address.value=reinterpret_cast<VAddr>(indices.data());regs.num_indices=4;
 regs.index_offset=u32(-3);regs.enable_primitive_restart=1;
 r.PrepareVertexFetch(&pipeline,true,2);
 if(argc>1){assert(!r.vertex_fetch.direct && !r.vertex_fetch.indices_ready && memory.copies==0);puts("PASS: disabled direct vertex range control preserves original index/upload path.");return 0;}
 assert(r.vertex_fetch.direct && r.vertex_fetch.indices_ready && r.vertex_fetch.records==Vulkan::Motion::VertexRange(97,8));
 const auto captured=r.buffer_cache.stream.bound;indices[2]=600;
 assert(r.buffer_cache.stream.bound==captured && r.vertex_fetch.records.first==97);
 assert(!std::memcmp(captured.data(),r.vertex_fetch.indices.data(),captured.size()));
 assert(r.index_bind.offset==128 && r.index_bind.type==vk::IndexType::eUint16);
 r.buffer_cache.gpu_written=true;r.PrepareVertexFetch(&pipeline,true,2);assert(!r.vertex_fetch.indices_ready && !r.vertex_fetch.direct);
 r.buffer_cache.gpu_written=false;memory.safe=false;r.PrepareVertexFetch(&pipeline,true,2);assert(!r.vertex_fetch.direct);
 memory.safe=true;regs.primitive_restart_index=12;r.PrepareVertexFetch(&pipeline,true,2);assert(!r.vertex_fetch.direct);
 regs.primitive_restart_index=0xffff;regs.num_indices=10000;r.PrepareVertexFetch(&pipeline,true,2);assert(!r.vertex_fetch.direct);
 regs.index_offset=7;regs.num_indices=20;r.PrepareVertexFetch(&pipeline,false,0);
 assert(r.vertex_fetch.direct && !r.vertex_fetch.indices_ready && r.vertex_fetch.records==Vulkan::Motion::VertexRange(7,20));
 std::vector<u32> wide={2,9,0xffffffffu};regs.index_base_address.value=reinterpret_cast<VAddr>(wide.data());
 regs.index_buffer_type.index_type=AmdGpu::IndexType::Index32;regs.primitive_restart_index=0xffffffffu;regs.num_indices=3;regs.index_offset=0;
 r.PrepareVertexFetch(&pipeline,true,0);assert(r.vertex_fetch.records==Vulkan::Motion::VertexRange(2,8) && r.index_bind.type==vk::IndexType::eUint32);
 pipeline.fetch.reset();r.PrepareVertexFetch(&pipeline,true,0);assert(!r.vertex_fetch.direct && !r.vertex_fetch.indices_ready);
 puts("PASS: 30000 byte-coverage cases and actual PrepareVertexFetch: bound index snapshot equals scanned data, 16/32-bit/restart/signed base/nonindexed ranges, mutable-source isolation, GPU-written/unsafe/large/custom-restart/no-fetch fallbacks.");
}
'''.replace('@METHOD@',method)
with tempfile.TemporaryDirectory(prefix='vertex-fetch-ranges-') as directory:
 p=Path(directory)/'ranges.cpp';p.write_text(fixture);exe=p.with_suffix('')
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shadps4'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=20)
 subprocess.run([str(exe),'control'],env={**os.environ,'BB_VERTEX_FETCH_RANGES':'0'},check=True,timeout=20)
