# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute production resource retirement with a semaphore advancing at Refresh."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE = 'a93ce851256ce41acc2953539a2ada3bd12de7f8'
SOURCE = 'gpu/shadps4/video_core/renderer_vulkan/vk_resource_pool.cpp'
PROGRAM = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <optional>
#include <vector>
using u64=uint64_t;
namespace Vulkan {
struct Semaphore {
 u64 known{},completed{},current{1};unsigned refreshes{};
 u64 KnownGpuTick(){return known;}u64 CurrentTick(){return current;}
 void Refresh(){known=completed;++refreshes;}
};
__DECLARATION__
__METHODS__
struct Pool:ResourcePool {
 using ResourcePool::CommitResource;
 unsigned allocations{};
 Pool(Semaphore* semaphore):ResourcePool{semaphore,4}{}
 void Allocate(size_t,size_t) override {++allocations;}
 size_t Capacity(){return ticks.size();}
};
}
int main(){
 using namespace Vulkan;
 Semaphore semaphore;Pool pool{&semaphore};
 for(unsigned i=0;i<4;++i)assert(pool.CommitResource()==i);
 assert(pool.Capacity()==4 && pool.allocations==1);
 semaphore.completed=1;semaphore.current=2;
 const auto first=pool.CommitResource();
#if CURRENT
 assert(first==0 && pool.Capacity()==4 && pool.allocations==1);
 for(unsigned tick=2;tick<200;++tick){
  semaphore.current=tick;
  for(unsigned i=1;i<4;++i)pool.CommitResource();
  semaphore.completed=tick;semaphore.current=tick+1;
  assert(pool.CommitResource()==0 && pool.Capacity()==4 && pool.allocations==1);
 }
 // Genuine pressure still grows; it must never reuse a non-retired buffer.
 for(unsigned i=0;i<4;++i)pool.CommitResource();
 assert(pool.Capacity()==8 && pool.allocations==2);
 std::puts("PASS: actual resource pool reuses freshly retired command buffers across 199 refreshes; real in-flight pressure still allocates safely.");
#else
 assert(first==4 && pool.Capacity()==8 && pool.allocations==2);
 std::puts("R41 CONTROL: semaphore refresh retires all four buffers, but stale captured tick forces another allocation.");
#endif
}
'''


def main():
    header = (ROOT/'gpu/shadps4/video_core/renderer_vulkan/vk_resource_pool.h').read_text()
    declaration = header[header.index('class ResourcePool {'):header.index('class CommandPool final')]
    with tempfile.TemporaryDirectory(prefix='resource-retirement-') as temp:
        folder = Path(temp)
        for current in (False, True):
            code = ((ROOT/SOURCE).read_text() if current else
                    subprocess.check_output(['git','show',BASE+':'+SOURCE],cwd=ROOT,text=True))
            methods = code[code.index('ResourcePool::ResourcePool('):code.index('constexpr std::size_t COMMAND_BUFFER_POOL_SIZE')]
            cpp = folder/('current.cpp' if current else 'revision41.cpp')
            cpp.write_text(PROGRAM.replace('__DECLARATION__', declaration).replace('__METHODS__', methods))
            exe = cpp.with_suffix('')
            subprocess.run(['g++','-std=c++20','-O1','-Wall','-Wextra','-Werror','-DCURRENT='+str(int(current)),str(cpp),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)


if __name__ == '__main__':
    main()
