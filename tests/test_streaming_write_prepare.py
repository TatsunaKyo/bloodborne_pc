# SPDX-License-Identifier: GPL-2.0-or-later
# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
"""Exercise actual I/O write preparation on protected pages; no game is simulated."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from test_streaming_io import function

root=Path(__file__).resolve().parents[1]
prefix=r'''
#define _GNU_SOURCE
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <signal.h>
#include <sys/mman.h>
#include <unistd.h>
#define USER_MIN UINT64_C(0x1000000000)
#define USER_MAX UINT64_C(0xfc00000000)
static void (*hook_invalidate)(uintptr_t,uint64_t);
'''
main=r'''
static unsigned faults,notifications;
static uintptr_t begin,end;
static void fault(int signal,siginfo_t* info,void* context) {
    (void)signal;(void)context;
    uintptr_t page=(uintptr_t)info->si_addr & ~(uintptr_t)4095;
    if(page<begin || page>=end)_exit(3);
    ++faults;
    if(mprotect((void*)page,4096,PROT_READ|PROT_WRITE))_exit(4);
}
static void invalidate(uintptr_t address,uint64_t size) {
    assert(address>=begin && size<=end-address);++notifications;
    uintptr_t low=address & ~(uintptr_t)4095;
    uintptr_t high=(address+size+4095)&~(uintptr_t)4095;
    assert(!mprotect((void*)low,high-low,PROT_READ|PROT_WRITE));
}
int main(void) {
    const size_t size=3*1024*1024;
    void* memory=mmap((void*)(USER_MIN+0x40000000),size,PROT_READ|PROT_WRITE,
        MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
    assert(memory!=MAP_FAILED);begin=(uintptr_t)memory;end=begin+size;
    for(size_t i=0;i<size;i++)((unsigned char*)memory)[i]=(unsigned char)(i*117+(i>>12));
    unsigned char* original=malloc(size);assert(original);memcpy(original,memory,size);
    struct sigaction handler={0};handler.sa_sigaction=fault;handler.sa_flags=SA_SIGINFO;
    assert(!sigaction(SIGSEGV,&handler,NULL));
    assert(!mprotect(memory,size,PROT_READ));
    touch_for_write(memory,size);
    assert(faults==size/4096 && notifications==0 && !memcmp(original,memory,size));
    unsigned old_faults=faults;faults=0;
    assert(!mprotect(memory,size,PROT_READ));hook_invalidate=invalidate;
    touch_for_write(memory,size);
    assert(!faults && notifications==3 && !memcmp(original,memory,size));
    // Unaligned spans, small reads, zero, wrapping/non-guest pointers, missing hook.
    notifications=0;assert(!mprotect(memory,size,PROT_READ));
    touch_for_write((char*)memory+19,size-37);
    assert(!faults && notifications==3 && !memcmp(original,memory,size));
    notifications=0;faults=0;assert(!mprotect(memory,size,PROT_READ));
    touch_for_write(memory,8192);assert(faults==2 && notifications==0);
    runtime_memory_prepare_io_write(USER_MIN-1,65536);
    runtime_memory_prepare_io_write(USER_MAX-10,65536);
    runtime_memory_prepare_io_write(begin,UINT64_MAX);
    runtime_memory_prepare_io_write(begin,0);assert(!notifications);
    hook_invalidate=NULL;runtime_memory_prepare_io_write(begin,size);assert(!notifications);
    assert(!memcmp(original,memory,size));free(original);assert(!munmap(memory,size));
    printf("PASS: 3 MiB protected destination: %u page faults -> 3 range notifications, identical bytes; fallbacks/bounds retained.\n",old_faults);
}
'''
with tempfile.TemporaryDirectory(prefix='bb-streaming-write-') as tmp:
    source=Path(tmp)/'streaming-write.c';binary=Path(tmp)/'streaming-write'
    source.write_text(prefix+'\n'+function((root/'src/runtime_memory.c').read_text(),'runtime_memory_prepare_io_write')+'\n'+function((root/'src/runtime_file.c').read_text(),'touch_for_write')+main)
    subprocess.run(shlex.split(os.environ.get('CC','cc'))+['-std=c11','-O1','-Wall','-Wextra',str(source),'-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
