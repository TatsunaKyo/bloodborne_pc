"""Compile the actual runtime VMA/cache implementation and validate upload guards."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[1]
fixture=r'''
#include "runtime_memory.c"
#include <assert.h>
uint64_t runtime_disabled_optimizations;
unsigned full_waits,range_waits;
void full_wait(void){++full_waits;}
void range_wait(uintptr_t a,uint64_t n){assert(a && n);++range_waits;}
void enqueue(uintptr_t a,uint64_t n,uint32_t p,uintptr_t d){(void)a;(void)n;(void)p;(void)d;}
int main(void){
 const uintptr_t base=0x1000000;
 write_lock();
 assert(!vma_insert(0,(Vma){base,base+65536,KIND_DIRECT,0x33,0,0}));
 assert(!vma_insert(1,(Vma){base+65536,base+131072,KIND_DIRECT,0x33,0,65536}));
 write_unlock();
 assert(runtime_memory_can_read_ahead(base,131072));
 assert(runtime_memory_can_read_ahead(base+61440,8192));
 assert(!runtime_memory_can_read_ahead(base-1,10));
 assert(!runtime_memory_can_read_ahead(base,131073));
 assert(!runtime_memory_can_read_ahead(base,0));
 assert(!runtime_memory_can_read_ahead(UINTPTR_MAX-3,8));
 for(unsigned i=0;i<10000;++i)assert(runtime_memory_can_read_ahead(base,65536));
 write_lock();vmas[0].prot=0;write_unlock();
 assert(!runtime_memory_can_read_ahead(base,65536)); // cached permission must expire
 assert(!runtime_memory_can_read_ahead(base+61440,8192));
 write_lock();vmas[0].prot=0x10;write_unlock();
 assert(runtime_memory_can_read_ahead(base,65536)); // GPU-readable guest allocation
 write_lock();vmas[1].kind=KIND_RESERVED;write_unlock();
 assert(!runtime_memory_can_read_ahead(base,131072));
 assert(!runtime_memory_can_read_ahead(base+65536,1));
 runtime_memory_set_protection_hooks(enqueue,full_wait);
 runtime_memory_set_range_protection_hook(range_wait);
 runtime_memory_wait_page_protection_range(base,4096);assert(range_waits==1 && !full_waits);
 runtime_memory_wait_page_protection_range(base,131072);assert(full_waits==1);
 runtime_memory_wait_page_protection_range(base,0);assert(full_waits==1 && range_waits==1);
 runtime_memory_wait_page_protection_range(UINTPTR_MAX-3,8);assert(full_waits==2);
 write_lock();vmas[0].prot=0;write_unlock();
 runtime_memory_wait_page_protection_range(base,4096);assert(full_waits==3);
 write_lock();vmas[0].prot=0x33;vmas[0].kind=KIND_FLEXIBLE;write_unlock();
 runtime_memory_wait_page_protection_range(base,4096);assert(full_waits==4);
 write_lock();vmas[0].kind=KIND_DIRECT;write_unlock();
 runtime_memory_set_range_protection_hook(NULL);
 runtime_memory_wait_page_protection_range(base,4096);assert(full_waits==5);
 runtime_memory_set_protection_hooks(NULL,NULL);
 write_lock();vmas[1].kind=KIND_DIRECT;vmas[1].start+=16384;write_unlock();
 assert(!runtime_memory_can_read_ahead(base,131072)); // VMA gap
 // A newly created physical alias invalidates the cached eligibility.
 write_lock();
 assert(!vma_insert(2,(Vma){base+196608,base+262144,KIND_DIRECT,0x33,0,0}));
 write_unlock();
 assert(!runtime_memory_can_read_ahead(base,65536));
 write_lock();vma_erase(2,1);write_unlock();
 assert(runtime_memory_can_read_ahead(base,65536));
 // Flexible memory is deliberately outside the speculative upload policy.
 write_lock();vmas[0].kind=KIND_FLEXIBLE;write_unlock();
 assert(!runtime_memory_can_read_ahead(base,65536));
 write_lock();vmas[0].kind=KIND_DIRECT;write_unlock();
 runtime_disabled_optimizations=1;
 assert(runtime_memory_can_read_ahead(base,65536));
 assert(!runtime_memory_can_read_ahead(base,131072));
 puts("PASS: actual runtime VMA guard, cache generation, adjacent mappings, reserved/inaccessible padding, gaps, GPU-readable permissions, overflow and cache-disabled control, physical alias creation/removal and flexible-memory exclusion.");
}
'''
with tempfile.TemporaryDirectory(prefix='memory-readable-') as directory:
    root=Path(directory);source=root/'fixture.c';source.write_text(fixture);exe=root/'fixture'
    subprocess.run([os.environ.get('CC','gcc'),'-std=gnu11','-O2','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'src'),str(source),'-pthread','-Wl,--gc-sections','-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
