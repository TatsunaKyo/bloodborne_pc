"""Run production texture-refresh/hash/invalidation methods with separate CPU/GPU bytes.

The fixture supplies completed buffer transfers; no GPU or frame-rate measurement
is implied. A tail-byte CPU write must survive hash reuse and live debug toggles.
"""
from pathlib import Path
import os, subprocess, tempfile

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'gpu/shadps4/video_core/texture_cache/texture_cache.cpp').read_text()
HEADER=(ROOT/'gpu/shadps4/video_core/texture_cache/image.h').read_text()
CPP=r'''
#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <cassert>
#include <cstring>
#include <future>
#include <iostream>
#include <mutex>
#include <vector>
#include <boost/container/small_vector.hpp>
#define XXH_INLINE_ALL
#include <xxhash.h>
#include "common/types.h"
#include "common/enum.h"
#include "video_core/renderer_vulkan/vk_common.h"
#include "bbport_toggles.h"
#include "bbport_hitch.h"
extern "C" {std::uint64_t runtime_disabled_optimizations=0;}
std::atomic<u64> hash_calls=0;
u64 CountedHash(const void* p,size_t n){++hash_calls;return XXH3_64bits(p,n);}
#undef XXH3_64bits
#define XXH3_64bits CountedHash
#define RENDERER_TRACE ((void)0)
#define TRACE_HINT(...) ((void)0)
template<class T,size_t N>using SmallVector=boost::container::small_vector<T,N>;
namespace Core {struct Memory {static Memory* Instance(){static Memory m;return &m;}void WaitForPageProtection(VAddr,u64){}};}
namespace BbCopy {
bool workers=true;
bool Enabled(){return workers;}
template<class F>void ParallelFor(size_t count,F fn){
 std::vector<std::future<void>> jobs;for(size_t i=0;i<count;++i)jobs.push_back(std::async(std::launch::async,[=]{fn(i);}));for(auto& job:jobs)job.get();
}
}
namespace BbPrompts {void OnUpload(VAddr,u64,u32,u32,u32,u32){}}
namespace VideoCore {
@FLAGS@
using ImageId=u32;
struct Image {
 struct Info {
  VAddr guest_address{};u64 guest_size{};u32 num_samples=1,num_bits=32;
  struct {u32 layers=1,levels=1;}resources;
  struct {u32 width=1,height=1,depth=1;}size;
  struct {bool is_volume=false;}props;
  struct Mip {u64 size;u32 pitch,height;u64 offset;};std::vector<Mip> mips_layout;
 }info;
 struct {bool storage=false,render_target=true,depth_target=false;}usage;
 VAddr guest_begin{},guest_end{},track_addr{},track_addr_end{};
 bool mip_hashes_current=false;u64 cpu_hash=0;std::array<u64,16> mip_hashes{};
 ImageFlagBits flags=CpuDirty;vk::ImageAspectFlags aspect_mask=vk::ImageAspectFlagBits::eColor;
 std::mutex mutex;std::vector<u8> gpu_buffer,pixels;u64 uploads=0;
 bool Overlaps(VAddr a,u64 n)const{return a<guest_end&&a+n>guest_begin;}
};
struct PageManager {static VAddr GetPageAddr(VAddr a){return a&~VAddr(4095);}static VAddr GetNextPageAddr(VAddr a){return (a+4096)&~VAddr(4095);}};
struct Scheduler{void EndRendering(){}};
struct BufferCache {
 Image* image;
 std::pair<const std::vector<u8>*,u64> ObtainBufferForImage(VAddr,u64){
  if(True(image->flags&GpuDirty)&&False(image->flags&CpuDirty))return {&image->gpu_buffer,0};
  static std::vector<u8> guest;guest.assign(reinterpret_cast<const u8*>(image->info.guest_address),reinterpret_cast<const u8*>(image->info.guest_address)+image->info.guest_size);return {&guest,0};
 }
};
struct TileManager {std::pair<const std::vector<u8>*,u64> DetileImage(const std::vector<u8>* p,u64 n,const Image::Info&){return {p,n};}};
struct Runtime {
 void UploadImage(Image* image,const std::vector<u8>* buffer,const auto& copies){
  for(auto copy:copies){const auto& mip=image->info.mips_layout[copy.imageSubresource.mipLevel];memcpy(image->pixels.data()+mip.offset,buffer->data()+copy.bufferOffset,mip.size);}
  image->flags&=~Dirty;++image->uploads;
 }
};
struct Slots {Image* image;Image& operator[](ImageId){return *image;}};
class TextureCache {
public:
 std::mutex mutex;Slots slot_images;Scheduler scheduler;BufferCache buffer_cache;TileManager tile_manager;Runtime runtime;
 explicit TextureCache(Image& i):slot_images{&i},buffer_cache{&i}{}
 template<class F>void ForEachImageInRegion(VAddr,u64,F fn){fn(0,*slot_images.image);}
 void UntrackImage(ImageId){auto& i=*slot_images.image;i.mip_hashes_current=false;i.track_addr=i.track_addr_end=0;}
 void UntrackImageHead(ImageId i){UntrackImage(i);}void UntrackImageTail(ImageId i){UntrackImage(i);}
 u64 MaybeDirtyHash(const Image&);void MarkAsMaybeDirty(ImageId,Image&);void InvalidateMemory(VAddr,size_t);void RefreshImage(Image&);
};
@METHODS@
}
using namespace VideoCore;
int main(){
 for(u64 bytes:{4ull,4ull*1024*1024}){
  std::vector<u8> cpu(bytes,7);Image image;image.info.guest_address=reinterpret_cast<VAddr>(cpu.data());image.info.guest_size=bytes;
  image.info.size.width=u32(bytes/4);image.info.mips_layout={{bytes,0,0,0}};
  image.guest_begin=image.info.guest_address;image.guest_end=image.guest_begin+bytes;
  image.gpu_buffer.assign(bytes,31);image.pixels.assign(bytes,0);TextureCache cache(image);
  auto track=[&]{image.track_addr=image.guest_begin;image.track_addr_end=image.guest_end;};
  track();cache.RefreshImage(image);assert(image.pixels==cpu&&image.mip_hashes_current);
  auto calls=hash_calls.load();
  for(unsigned i=0;i<1000;++i){image.flags=GpuModified|GpuDirty;cache.RefreshImage(image);assert(image.pixels==image.gpu_buffer);}
  assert(hash_calls==calls);
  cache.InvalidateMemory(image.guest_end-1,1);cpu.back()=99;track();cache.RefreshImage(image);assert(image.pixels==cpu&&image.pixels.back()==99);
  // Every supported worker/debug mode hashes the same bytes to the same value.
  BbCopy::workers=true;runtime_disabled_optimizations=0;auto parallel=GuestMemoryHash(cpu.data(),bytes);
  BbCopy::workers=false;assert(GuestMemoryHash(cpu.data(),bytes)==parallel);
  BbCopy::workers=true;runtime_disabled_optimizations=BbToggle::ParallelImageHash;assert(GuestMemoryHash(cpu.data(),bytes)==parallel);
  runtime_disabled_optimizations=BbToggle::KeepMipHashes;calls=hash_calls.load();
  image.flags=GpuModified|GpuDirty;cache.RefreshImage(image);assert(hash_calls>calls&&image.pixels==image.gpu_buffer);
  runtime_disabled_optimizations=0;
  std::cout<<"PASS: "<<bytes<<"-byte target, 1000 GPU refreshes without rehashing; tail-byte CPU writes preserved; worker/debug digests identical.\n";
 }
 // Ordinary large textures do not claim a baseline when their upload skipped hashing.
 std::vector<u8> cpu(4*1024*1024,9);Image image;image.info.guest_address=reinterpret_cast<VAddr>(cpu.data());image.info.guest_size=cpu.size();
 image.info.size.width=u32(cpu.size()/4);image.info.mips_layout={{cpu.size(),0,0,0}};image.guest_begin=image.info.guest_address;image.guest_end=image.guest_begin+cpu.size();
 image.track_addr=image.guest_begin;image.track_addr_end=image.guest_end;image.usage.render_target=false;image.pixels.resize(cpu.size());image.gpu_buffer.assign(cpu.size(),81);
 TextureCache cache(image);cache.RefreshImage(image);assert(!image.mip_hashes_current);
 image.usage.storage=true;image.flags=GpuDirty;auto calls=hash_calls.load();cache.RefreshImage(image);assert(hash_calls>calls&&image.mip_hashes_current&&image.pixels==image.gpu_buffer);
 std::cout<<"PASS: promotion of an unhashed large texture records its first valid baseline.\n";
}
'''

def method(name):
    start=SOURCE.index(name);end=SOURCE.index('{',start)+1;depth=1
    while depth:
        depth+=(SOURCE[end]=='{')-(SOURCE[end]=='}');end+=1
    return SOURCE[start:end]

flags=HEADER[HEADER.index('enum ImageFlagBits'):HEADER.index('struct UniqueImage')]
methods='\n'.join(method(n) for n in ('static u64 GuestMemoryHash(', 'static bool KeepMipHashes(', 'u64 TextureCache::MaybeDirtyHash(', 'void TextureCache::MarkAsMaybeDirty(', 'void TextureCache::InvalidateMemory(', 'void TextureCache::RefreshImage('))
xxhash=ROOT.parent/'windows-build/sysroot/clang64/include'
with tempfile.TemporaryDirectory(prefix='texture-hashes-') as temporary:
    cpp=Path(temporary)/'test.cpp';cpp.write_text(CPP.replace('@FLAGS@',flags).replace('@METHODS@',methods));exe=cpp.with_suffix('')
    subprocess.run([os.environ.get('CXX','g++'),'-std=c++20','-O1','-pthread','-I'+str(ROOT/'gpu/shim'),'-I'+str(ROOT/'gpu/shadps4'),'-I'+str(ROOT/'out/test-headers'),'-idirafter',str(xxhash),str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True,timeout=90)
