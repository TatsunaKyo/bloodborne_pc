// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "bbport_page_watch_queue.h"
#include "bbport_toggles.h"
#include <cstdio>
#include <cstdlib>

#ifdef _WIN32
extern "C" {
void runtime_memory_apply_page_protection(uintptr_t, uint64_t, uint32_t);
void runtime_memory_set_protection_hooks(void (*)(uintptr_t,uint64_t,uint32_t,uintptr_t), void (*)());
}
#endif
namespace BbPageWatch {
#ifdef _WIN32
static void Apply(uintptr_t address, uint64_t bytes, uint32_t protection) {
    BbStats::Timer timer{BbStats::t_protect};
    runtime_memory_apply_page_protection(address, bytes, protection);
}
#endif
void Install() {
#ifdef _WIN32
    static const bool installed = [] {
        const char* value = std::getenv("BB_ASYNC_PAGE_WATCH");
        if (value && value[0] == '0') {
            std::puts("GPU: page protection worker disabled; synchronous control");
            return false;
        }
        // Runtime threads can end via _Exit. Keep this service alive as long as
        // guest threads can access the process mappings, as with the renderer.
        static auto* queue = new Queue{&Apply};
        installed_queue.store(queue, std::memory_order_release);
        runtime_memory_set_protection_hooks(
            [](uintptr_t a, uint64_t n, uint32_t p, uintptr_t domain) { queue->Push(a,n,p,domain); },
            [] { queue->Wait(); });
        std::puts("GPU: ordered page protection worker active; snapshots and remaps wait for installation");
        return true;
    }();
    (void)installed;
#endif
}
} // namespace BbPageWatch
