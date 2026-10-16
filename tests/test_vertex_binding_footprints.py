"""Execute production demand merging/binding code with interleaved and instance streams."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp').read_text()
a=text.index('    // Map buffers for merged ranges',text.index('void Rasterizer::ResolveVertexBuffers('))
body=text[a:text.index('\n}\n',a)]
fixture=r'''
#include "video_core/buffer_cache/vertex_fetch_range.h"
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <tuple>
#include <vector>
using u32=uint32_t;using u64=uint64_t;using VAddr=uintptr_t;
template<class T>using VertexInputs=std::vector<T>;
#define ASSERT(x) assert(x)
#define VK_NULL_HANDLE 0
namespace vk{enum class VertexInputRate{eVertex,eInstance};}
struct GuestBuffer{VAddr base_address;u32 bytes,stride;u32 GetSize()const{return bytes;}u32 GetStride()const{return stride;}};
struct Binding{u32 binding;vk::VertexInputRate inputRate;};
struct Attribute{u32 binding,offset;};
constexpr VAddr Base=0x1000000;
struct GpuBuffer{int Handle()const{return 123;}}gpu_buffer;
struct BufferRange{VAddr base_address,end_address;const GpuBuffer* buffer{};u64 offset{};u64 GetSize()const{return end_address-base_address;}};
struct Memory{u64 ClampRangeSize(VAddr,u64 n){return n;}}mem;
struct Cache{
 std::array<uint8_t,256*1024> source{},gpu{};u64 bytes{};
 std::pair<const GpuBuffer*,u64> ObtainBuffer(VAddr a,u32 n,bool){
  std::memcpy(gpu.data()+a-Base,source.data()+a-Base,n);bytes+=n;return {&gpu_buffer,a-Base};
 }
 std::pair<const GpuBuffer*,u64> ObtainVertexBuffer(VAddr a,u32,std::span<const VideoCore::VertexFetch::Range> reads){
  for(auto r:reads){std::memcpy(gpu.data()+a-Base+r.offset,source.data()+a-Base+r.offset,r.size);bytes+=r.size;}
  return {&gpu_buffer,a-Base};
 }
}buffer_cache;
struct Runtime{bool IsBufferAccessed(const GpuBuffer*,u64,u64){return false;}}runtime;
struct Prepared{std::array<uint8_t,3> range_index{0,0,1};};
struct BindState{std::vector<int> host_buffers;std::vector<u64> host_offsets,host_sizes,host_strides;u32 num_buffers{};};
void Run(bool limited,bool prepared){
 auto* memory=&mem;bool needs_barrier=false;
 struct{struct{u32 first,count;}records{100,10};bool direct;}vertex_fetch{{100,10},limited};
 BindState v;Prepared p;const Prepared* ready=prepared?&p:nullptr;
 std::vector<GuestBuffer> guest_buffers={{Base,65536,32},{Base+16,65520,32},{Base+131072,32768,64}};
 std::vector<Binding> bindings={{4,vk::VertexInputRate::eVertex},{7,vk::VertexInputRate::eVertex},{9,vk::VertexInputRate::eInstance}};
 std::vector<Attribute> attributes={{4,0},{7,0},{9,0}};
 VertexInputs<BufferRange> ranges_merged={{Base,Base+65536},{Base+131072,Base+163840}};
 @BODY@
 assert(!needs_barrier && v.num_buffers==3);
 assert((v.host_offsets==std::vector<u64>{0,16,131072}));
 assert((v.host_sizes==std::vector<u64>{65536,65520,32768}));
 assert(buffer_cache.bytes==(limited?32768+336:65536+32768));
 for(u32 stream=0;stream<2;++stream)for(u32 record=100;record<110;++record)for(u32 byte=0;byte<16;++byte){
  const auto at=v.host_offsets[stream]+record*v.host_strides[stream]+byte;
  assert(buffer_cache.gpu[at]==buffer_cache.source[at]);
 }
 for(u32 at=131072;at<163840;++at)assert(buffer_cache.gpu[at]==buffer_cache.source[at]);
}
int main(){
 for(bool limited:{false,true})for(bool prepared:{false,true}){
  buffer_cache.gpu.fill(0);buffer_cache.bytes=0;
  for(u32 i=0;i<buffer_cache.source.size();++i)buffer_cache.source[i]=uint8_t(i*61+(i>>13)+5);
  Run(limited,prepared);
 }
 puts("PASS: actual ResolveVertexBuffers demand merge and binding code: interleaved streams, nonsequential attribute bindings, prepared/plain paths, full instance data, unchanged binding offsets/sizes and every referenced vertex byte.");
}
'''.replace('@BODY@',body)
fixture=fixture.replace('#include <tuple>','#include <tuple>\n#include <span>')
with tempfile.TemporaryDirectory(prefix='vertex-binding-footprints-') as directory:
 p=Path(directory)/'binding.cpp';p.write_text(fixture);exe=p.with_suffix('')
 subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O2','-pthread','-I'+str(ROOT/'gpu/shadps4'),str(p),'-o',str(exe)],check=True)
 subprocess.run([str(exe)],check=True,timeout=20)
