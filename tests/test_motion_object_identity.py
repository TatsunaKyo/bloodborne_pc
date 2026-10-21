# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Replay production pose binding and vertex history when visibility changes.

The R33 control reads another object's history for a shared mesh and for an
unidentified instance batch. This tests host guide selection, not GPU gameplay.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
BASE='0236df43f5b62adfa64e82106b923f1745a2664d'
HEADER='gpu/shadps4/video_core/renderer_vulkan/motion_history.h'
READER='gpu/shadps4/video_core/renderer_vulkan/vk_rasterizer.cpp'
HARNESS=r'''
#include <cassert>
#include <cstdio>
#include <optional>
#include <vector>
#define XXH_INLINE_ALL
#include "xxhash.h"
#include "bbport_hitch.h"
#include "motion_history.h"
namespace Motion=Vulkan::Motion;
using u32=uint32_t;using u64=uint64_t;using VAddr=uint64_t;
struct VS;
struct Sharp {
    std::vector<std::byte>* data{};
    bool Valid() const{return data && !data->empty();}
    u32 GetSize() const{return u32(data->size());}
    u32 GetStride() const{return 16;}
    VAddr base_address{};
};
struct Resource {
    std::vector<std::byte>* data{};
    bool IsSpecial() const{return false;}
    Sharp GetSharp(const VS&) const{return {data,u64(reinterpret_cast<uintptr_t>(data->data()))};}
};
struct VS {u64 pgm_hash{0xb10c4f55};std::vector<Resource> buffers;};
struct RingBinding {u32 size{},offset{};};
RingBinding ring;bool use_ring;
const RingBinding* FindRingBinding(const VS&,u32 i){return use_ring && i==0?&ring:nullptr;}
struct Memory {
    bool IsValidGpuMapping(VAddr a,int) const{return a!=0;}
    u64 ClampRangeSize(VAddr,u64 n) const{return n;}
} mapping;
struct Cache {bool IsRegionGpuModified(VAddr,u64) const{return false;}} cache;
struct Ring {std::vector<std::byte> data;const std::byte* Data(u32 n){return data.data()+n;}} constants;
struct Binding {u64 palette{},model{},pose{};bool gated{},valid{};};
Binding ReadBindings(const VS& vs){
    const bool all_motion=false;
    auto*memory=&mapping;auto*constant_ring=&constants;auto&buffer_cache=cache;
    const u32 num_ring_stages=use_ring?1:0;
__READER__
    return {palette,model_batch,
#if CURRENT
            pose_binding,
#else
            0,
#endif
            gated,model_batch_seen && model_batch_valid};
}
Motion::Draw Draw(const VS&vs,u32 instances=1){
    const auto b=ReadBindings(vs);assert(b.valid);
    Motion::Draw d{.shader=vs.pgm_hash,.geometry=2,.indices=3,.topology=4,
                  .model_batch=b.model,
#if CURRENT
                  .pose_binding=b.pose,
#endif
                  .index_count=8,.instances=instances,.vertices={0,8}};
    return d;
}
Motion::History::GateKey Gate(const VS&vs){
    auto b=ReadBindings(vs);
    return {.shader=vs.pgm_hash,.geometry=2,.indices=3,.model_batch=b.model,
#if CURRENT
            .pose_binding=b.pose,
#endif
            .index_count=8,.instances=1};
}
int main(){
    std::vector<std::byte> bone_a(2304),bone_b(2304),secondary_a(192),secondary_b(192);
    VS actor_a{0xb10c4f55,{{&bone_a}}},actor_b{0xb10c4f55,{{&bone_b}}};
    Motion::History actors(128);
    const auto a=actors.Prepare(Draw(actor_a));assert(a.store && !a.load);
    actors.NextFrame();
    const auto b=actors.Prepare(Draw(actor_b));
#if CURRENT
    assert(!b.load && b.store);
    assert(ReadBindings(actor_a).pose && ReadBindings(actor_a).pose!=ReadBindings(actor_b).pose);
#else
    assert(b.load==a.store);
    std::puts("CONTROL: R33 retrieves object A's positions when a different pose binding uses its mesh.");
#endif
    actors.NextFrame();bone_b[0]=std::byte{1};
    assert(actors.Prepare(Draw(actor_b)).load==b.store);
    // Every bound pose contributes, including one following a character palette.
    VS multi_a{0xb10c4f55,{{&bone_a},{&secondary_a}}};
    VS multi_b{0xb10c4f55,{{&bone_a},{&secondary_b}}};
    Motion::History multiple(128);
    const auto ma=multiple.Prepare(Draw(multi_a));multiple.NextFrame();
    const auto mb=multiple.Prepare(Draw(multi_b));
#if CURRENT
    assert(!mb.load && ReadBindings(multi_a).pose!=ReadBindings(multi_b).pose);
#else
    assert(mb.load==ma.store);
    std::puts("CONTROL: R33 stops at the first skeleton and aliases changed later pose bindings.");
#endif
    Motion::History batch(128);
    const auto batch_a=batch.Prepare(Draw(actor_a,2));batch.NextFrame();
    const auto batch_b=batch.Prepare(Draw(actor_a,2));
#if CURRENT
    assert(!batch_a.store && !batch_a.load && !batch_b.store && !batch_b.load);
    assert(batch.stats.unidentified_batches==2);
#else
    assert(batch_b.load==batch_a.store && batch_a.store);
    std::puts("CONTROL: R33 retrieves prior instance-slot positions without knowing which objects occupy the slots.");
#endif
    // Verified ordered world records still retain their animated motion.
    std::vector<std::byte> models(832),wind(768),relocated_wind(768);
    VS tree{Motion::ModelBatchShader,{{&models},{&wind}}};
    Motion::History verified(128);
    const auto va=verified.Prepare(Draw(tree,2));verified.NextFrame();
    assert(verified.Prepare(Draw(tree,2)).load==va.store && va.store);
    assert(Motion::CameraBounded(Draw(tree,2)));
    verified.NextFrame();
    VS relocated_tree{Motion::ModelBatchShader,{{&models},{&relocated_wind}}};
    assert(verified.Prepare(Draw(relocated_tree,2)).load);
    // A weapon can animate its palette under a stable entity identity.
    VS weapon{7,{{&secondary_a}}};Motion::History weapons(64);
    assert(!weapons.Moving(Gate(weapon),ReadBindings(weapon).palette));weapons.NextFrame();
    secondary_a[0]=std::byte{1};
    assert(weapons.Moving(Gate(weapon),ReadBindings(weapon).palette));
    const auto wa=weapons.Prepare(Draw(weapon));weapons.NextFrame();secondary_a[0]=std::byte{2};
    assert(weapons.Moving(Gate(weapon),ReadBindings(weapon).palette));
    assert(weapons.Prepare(Draw(weapon)).load==wa.store);
    // Moving host ring offsets must not change an object's original guest binding.
    const auto ordinary=ReadBindings(weapon);
    use_ring=true;ring={192,0};constants.data.resize(384);
    std::copy(secondary_a.begin(),secondary_a.end(),constants.data.begin());
    const auto ring_a=ReadBindings(weapon);ring.offset=192;
    std::copy(secondary_a.begin(),secondary_a.end(),constants.data.begin()+192);
    const auto ring_b=ReadBindings(weapon);
    assert(ordinary.pose==ring_a.pose && ring_a.pose==ring_b.pose && ring_a.palette==ring_b.palette);
#if CURRENT
    std::puts("PASS: production pose-binding identity rejects another object and changed later palettes; unknown instance batches use camera guides.");
    std::puts("PASS: actor/weapon animation, verified world instances and host-ring relocation preserve their history.");
#endif
}
'''

def read(path,ref=None):
    return subprocess.check_output(['git','show',ref+':'+path],cwd=ROOT,text=True) if ref else (ROOT/path).read_text()

def prepare(folder):
    folder.mkdir(parents=True,exist_ok=True)
    for name,ref in [('revision33',BASE),('current',None)]:
        target=folder/name;target.mkdir(exist_ok=True)
        (target/'motion_history.h').write_text(read(HEADER,ref))
        source=read(READER,ref);start=source.index('        bool gated = !all_motion;')
        body=source[start:source.index('        push_data.motion_param = 0;',start)]
        (target/'test.cpp').write_text('#define CURRENT '+('0' if ref else '1')+'\n'+HARNESS.replace('__READER__',body))

def execute(folder):
    compiler=os.environ.get('CXX') or shutil.which('c++') or shutil.which('cl')
    if not compiler:raise RuntimeError('C++20 compiler required.')
    msvc=Path(compiler).name.lower() in ('cl','cl.exe')
    for name in ('revision33','current'):
        target=folder/name;exe=target/('test.exe' if os.name=='nt' else 'test')
        xxhash=ROOT/'gpu/third_party/xxhash'
        if not (xxhash/'xxhash.h').exists():
            candidates=[ROOT/'out/test-headers',Path('/workspace/scratch/489868675a17/windows-build/sysroot/clang64/include'),Path('/usr/include')]
            xxhash=next((p for p in candidates if (p/'xxhash.h').exists()),None)
        if xxhash is None:raise RuntimeError('xxhash.h required for the production binding reader.')
        # Isolate this portable header from a Windows sysroot's system headers.
        shutil.copy2(xxhash/'xxhash.h',target/'xxhash.h')
        args=([compiler,'/nologo','/O1','/EHsc','/std:c++20',str(target/'test.cpp'),'/Fe:'+str(exe)] if msvc else
              [compiler,'-std=c++20','-O1',str(target/'test.cpp'),'-o',str(exe)])
        args.append(('/I' if msvc else '-I')+str(ROOT/'gpu/shim'))
        subprocess.run(args,cwd=target,check=True,timeout=60)
        subprocess.run([str(exe)],check=True,timeout=20)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare',type=Path);args=parser.parse_args()
    if args.prepare:prepare(args.prepare.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix='bb-motion-identity-') as tmp:
            folder=Path(tmp);prepare(folder);execute(folder)
