// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_readback_batch.h"
#include "bbport_legacy_gpu.h"
#include <array>
#include <cassert>
#include <cstdio>
#include <vector>
int main() {
    for (const char* n : {"NVIDIA GeForce RTX 2060", "NVIDIA GeForce RTX 2080 Ti", "NVIDIA GeForce RTX 3050 Laptop GPU", "GeForce RTX 3090 Ti"})
        assert(bb_dlssg_mod_gpu(0x10de,n));
    for (const char* n : {"NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 5090", "NVIDIA GeForce GTX 1660", "NVIDIA RTX A4000", "GeForce RTX 20", "Radeon RTX 3080"})
        assert(!bb_dlssg_mod_gpu(0x10de,n));
    assert(!bb_dlssg_mod_gpu(0x1002,"GeForce RTX 3080"));
    assert(!bb_dlssg_mod_gpu(0x8086,"GeForce RTX 2080"));
    // Simulate GPU ownership and protected guest pages. A retirement of any page
    // before all readbacks in its group is an error, even if its own copy completed.
    std::array<unsigned,40> guest{}, gpu{};
    std::array<bool,40> protected_page{};
    std::vector<unsigned> recorded;
    unsigned waits=0,copies=0,released_staging=0,retired=0;
    bool gpu_complete=false;
    BbReadback::Batch batch{[&] { ++waits;gpu_complete=true; }};
    for (unsigned i=0;i<40;++i) {
        batch.Prepare(2*1024*1024);
        if (recorded.empty()) gpu_complete=false;
        gpu[i]=0xa500+i;protected_page[i]=true;recorded.push_back(i);
        batch.Copy(2*1024*1024,[&,i] {
            assert(gpu_complete && protected_page[i]);guest[i]=gpu[i];++copies;++released_staging;
        });
        batch.Retire([&,i] {
            for (auto j:recorded) assert(guest[j]==gpu[j]);
            assert(protected_page[i]);protected_page[i]=false;++retired;
            if (retired==copies) recorded.clear();
        });
    }
    batch.Flush();batch.Flush();
    assert(waits==3 && batch.Waits()==3 && released_staging==40 && retired==40);
    for (unsigned i=0;i<40;++i) assert(guest[i]==gpu[i] && !protected_page[i]);
    // Empty lists never wait; an individual oversized image is handled alone.
    batch.Prepare(128*1024*1024);assert(waits==3);
    batch.Copy(128*1024*1024,[&]{assert(gpu_complete);});
    batch.Prepare(1);assert(waits==4);batch.Flush();assert(waits==4);
    std::puts("PASS: 40 readbacks / 3 waits, bounded staging, all writes before page reuse, no empty waits, oversized image; real RTX 20/30 gate rejects RTX 40/50/GTX/other vendors.");
}
