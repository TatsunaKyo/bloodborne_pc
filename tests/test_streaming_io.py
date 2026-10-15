# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prepare a Windows test of the actual asset reader and guest read/close bodies."""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def function(source, name):
    start = re.search(r'^.*\b' + re.escape(name) + r'\([^\n]*\) \{', source, re.M).start()
    body = source.index('{', start)
    depth = 1
    end = body + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


PREFIX = r'''
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#include <cerrno>
#include <cstdint>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <chrono>
#include <thread>
#include <future>
#include <atomic>
#include <vector>
#include <string>
using ssize_t=int64_t;
using pthread_mutex_t=SRWLOCK;
using pthread_cond_t=CONDITION_VARIABLE;
#define PTHREAD_MUTEX_INITIALIZER SRWLOCK_INIT
#define PTHREAD_COND_INITIALIZER CONDITION_VARIABLE_INIT
int pthread_mutex_lock(pthread_mutex_t* m){AcquireSRWLockExclusive(m);return 0;}
int pthread_mutex_unlock(pthread_mutex_t* m){ReleaseSRWLockExclusive(m);return 0;}
int pthread_cond_wait(pthread_cond_t* c,pthread_mutex_t* m){return !SleepConditionVariableSRW(c,m,INFINITE,0);}
int pthread_cond_broadcast(pthread_cond_t* c){WakeAllConditionVariable(c);return 0;}
'''

MIDDLE = r'''
static std::atomic<bool> hold_reads{};
static std::atomic<int> entered{};
int64_t runtime_asset_read_at(void *reader,void* buffer,size_t size,int64_t offset){
    entered++;
    while(hold_reads) std::this_thread::yield();
    return ProductionReadAt(reader,buffer,size,offset);
}
static int64_t fallback_reads{};
ssize_t pread(int fd,void* p,size_t n,int64_t offset){
    ++fallback_reads;
    OVERLAPPED at{};at.Offset=DWORD(offset);at.OffsetHigh=DWORD(uint64_t(offset)>>32);
    DWORD count{};
    return ReadFile((HANDLE)_get_osfhandle(fd),p,DWORD(n),&count,&at) ? count : -1;
}
struct Listing {};
void free_listing(Listing* p){assert(!p);}
#define MAX_FILES 1024
#define USER_MIN UINT64_C(0x1000000000)
#define USER_MAX UINT64_C(0xfc00000000)
static void (*hook_invalidate)(uintptr_t,uint64_t);
'''

MAIN = r'''
static uintptr_t tracked_begin,tracked_end;
static std::atomic<unsigned> tracked_faults{},range_notices{};
static LONG CALLBACK PageFault(EXCEPTION_POINTERS* info){
    if(info->ExceptionRecord->ExceptionCode!=EXCEPTION_ACCESS_VIOLATION)return EXCEPTION_CONTINUE_SEARCH;
    uintptr_t page=info->ExceptionRecord->ExceptionInformation[1]&~uintptr_t(4095);
    if(page<tracked_begin || page>=tracked_end)return EXCEPTION_CONTINUE_SEARCH;
    DWORD old{};if(!VirtualProtect((void*)page,4096,PAGE_READWRITE,&old))return EXCEPTION_CONTINUE_SEARCH;
    ++tracked_faults;return EXCEPTION_CONTINUE_EXECUTION;
}
static void PrepareRange(uintptr_t address,uint64_t size){
    assert(address>=tracked_begin && size<=tracked_end-address);
    DWORD old{};assert(VirtualProtect((void*)address,size,PAGE_READWRITE,&old));++range_notices;
}
int main(){
    using namespace std::chrono_literals;
    wchar_t folder[MAX_PATH], path[MAX_PATH];
    assert(GetTempPathW(MAX_PATH,folder));assert(GetTempFileNameW(folder,L"bbr",0,path));
    int fd=_wopen(path,_O_RDWR|_O_BINARY);assert(fd>=0);
    std::vector<unsigned char> content(8*1024*1024);
    for(size_t i=0;i<content.size();++i)content[i]=static_cast<unsigned char>((i*113+(i>>12)*7)&255);
    assert(_write(fd,content.data(),unsigned(content.size()))==int(content.size()));
    // Sparse offset above 4 GiB exercises both halves of OVERLAPPED.Offset.
    const int64_t high=(int64_t(1)<<32)+8192;
    DWORD returned{};assert(DeviceIoControl((HANDLE)_get_osfhandle(fd),FSCTL_SET_SPARSE,nullptr,0,nullptr,0,&returned,nullptr));
    assert(_lseeki64(fd,high,SEEK_SET)==high);
    assert(_write(fd,"above-4G",8)==8);assert(_lseeki64(fd,27,SEEK_SET)==27);
    void* reader=runtime_asset_reader_open(fd);assert(reader);
    files[3].used=1;files[3].host=fd;files[3].asset_reader=reader;
    std::vector<std::future<void>> workers;
    const auto started=std::chrono::steady_clock::now();
    for(int worker=0;worker<8;++worker)workers.push_back(std::async(std::launch::async,[&,worker]{
        std::vector<unsigned char> bytes(32768);
        for(int i=0;i<128;++i){
            size_t offset=(size_t(worker)*7919+size_t(i)*64711)%(content.size()-bytes.size());
            assert(do_pread(3,bytes.data(),bytes.size(),int64_t(offset))==int64_t(bytes.size()));
            assert(!std::memcmp(bytes.data(),content.data()+offset,bytes.size()));
        }
    }));
    for(auto& worker:workers)worker.get();
    assert(_lseeki64(fd,0,SEEK_CUR)==27);
    assert(!fallback_reads);
    char bytes[32]{};
    assert(do_pread(3,bytes,8,high)==8 && !std::memcmp(bytes,"above-4G",8));
    assert(do_pread(3,bytes,32,high+4)==4 && !std::memcmp(bytes,"e-4G",4));
    assert(do_pread(3,bytes,32,high+8)==0);
    assert(do_pread(3,bytes,0,0)==0);
    assert(do_pread(3,bytes,4,-1)==-EINVAL);
    assert(do_pread(3,bytes,32,INT64_MAX-4)==-EINVAL);
    assert(runtime_asset_read_at(nullptr,bytes,1,0)==-1 && errno==EBADF);
    assert(_lseeki64(fd,0,SEEK_CUR)==27);
    const size_t tracked_size=3*1024*1024;
    void* tracked=VirtualAlloc((void*)(USER_MIN+0x40000000),tracked_size,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);
    assert(tracked);tracked_begin=(uintptr_t)tracked;tracked_end=tracked_begin+tracked_size;
    void* handler=AddVectoredExceptionHandler(1,PageFault);assert(handler);
    DWORD old{};assert(VirtualProtect(tracked,tracked_size,PAGE_READONLY,&old));
    // Control: production per-page fallback still works without a renderer hook.
    assert(do_pread(3,tracked,tracked_size,0)==int64_t(tracked_size));
    assert(tracked_faults==tracked_size/4096 && !range_notices);
    assert(!std::memcmp(tracked,content.data(),tracked_size));
    tracked_faults=0;hook_invalidate=PrepareRange;
    assert(do_pread(3,tracked,tracked_size,0)==int64_t(tracked_size));
    assert(!tracked_faults && !range_notices); // Writable staging skips GPU synchronization.
    assert(VirtualProtect(tracked,tracked_size,PAGE_READONLY,&old));
    assert(do_pread(3,tracked,tracked_size,4096)==int64_t(tracked_size));
    assert(!tracked_faults && range_notices==3);
    assert(!std::memcmp(tracked,content.data()+4096,tracked_size));
    hook_invalidate=nullptr;assert(RemoveVectoredExceptionHandler(handler));
    assert(VirtualFree(tracked,0,MEM_RELEASE));
    std::puts("PASS: Windows protected streaming destination: 768 page faults -> 3 range invalidations; exact file bytes.");
    std::printf("Windows asset IO: 1024 parallel offset reads, exact bytes/cursor and >4 GiB/EOF checks in %.2f ms\n",
        std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-started).count());
    hold_reads=true;const int before=entered;
    auto a=std::async(std::launch::async,[&]{char b[16];assert(do_pread(3,b,16,0)==16);});
    auto b=std::async(std::launch::async,[&]{char b[16];assert(do_pread(3,b,16,4096)==16);});
    auto deadline=std::chrono::steady_clock::now()+5s;
    while(entered<before+2 && std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
    assert(entered>=before+2); // No global file-table lock across pending asset reads.
    auto close=std::async(std::launch::async,[]{return do_close(3);});
    assert(close.wait_for(30ms)==std::future_status::timeout);
    {std::scoped_lock unused;}
    pthread_mutex_lock(&lock);bool closing=files[3].closing;pthread_mutex_unlock(&lock);assert(closing);
    assert(do_pread(3,bytes,8,0)==-EBADF);
    hold_reads=false;a.get();b.get();assert(close.get()==0);
    assert(!files[3].used && !files[3].pending_reads);
    assert(DeleteFileW(path));
    std::puts("PASS: production Windows asset reads overlap, preserve offsets and hold file lifetime until completion.");
}
'''


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    compat = (ROOT / 'src/compat_win.c').read_text()
    fs = (ROOT / 'src/runtime_file.c').read_text()
    reader = (ROOT / 'src/runtime_asset_io.c').read_text()
    memory = (ROOT / 'src/runtime_memory.c').read_text()
    file_type = re.search(r'typedef struct \{\n    int used, host;[\s\S]*?\} File;', fs).group()
    declarations = file_type + r'''
static File files[MAX_FILES];
static size_t reads;
static uint64_t bytes_read;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t reads_finished=PTHREAD_COND_INITIALIZER;
static int audio_trace(){return 0;}
static auto bb_atomic_add_fetch(auto* value,auto add,int){return std::atomic_ref(*value).fetch_add(add)+add;}
#define __atomic_add_fetch bb_atomic_add_fetch
#ifndef __ATOMIC_RELAXED
#define __ATOMIC_RELAXED 0
#endif
#define close _close
'''
    # Compile unchanged production bodies; the fixture only supplies the OS-facing
    # setup and an entry gate around the reader to verify descriptor lifetime.
    code = PREFIX + '#include <winioctl.h>\n#include <mutex>\n' + function(compat, 'compat_errno_from_win32')
    code += '\n#define runtime_asset_read_at ProductionReadAt\n' + reader + '\n#undef runtime_asset_read_at\n'
    code += MIDDLE + '\n' + function(memory, 'runtime_memory_prepare_io_write') + '\n' + declarations
    for name in ('get', 'host_fd', 'touch_for_write', 'do_close', 'do_pread'):
        code += '\n' + function(fs, name)
    code += MAIN.replace('    {std::scoped_lock unused;}\n', '')
    (directory / 'streaming-io.cpp').write_text(code, encoding='utf-8')
    print('Prepared production Windows streaming IO fixture')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path, required=True)
    prepare(parser.parse_args().prepare)
