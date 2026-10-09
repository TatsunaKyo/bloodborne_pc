/* SPDX-License-Identifier: GPL-2.0-or-later
 * Paused wall time, published by the Windows launcher before resuming the child.
 * Keep this clock independent of the SDL thread: that thread is suspended too. */
#include "runtime.h"
#include <stdlib.h>
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
static INIT_ONCE background_once = INIT_ONCE_STATIC_INIT;
static HANDLE background_mapping;
static const uint32_t *background_view;
static unsigned background_ready;

static BOOL CALLBACK background_open(PINIT_ONCE once, PVOID parameter, PVOID *context) {
    (void)once; (void)parameter; (void)context;
    const char *name = getenv("BB_BACKGROUND_CHANNEL");
    if (name && *name) background_mapping = OpenFileMappingA(FILE_MAP_READ, FALSE, name);
    if (background_mapping) {
        background_view = MapViewOfFile(background_mapping, FILE_MAP_READ, 0, 0, 32);
        if (!background_view || background_view[0] != UINT32_C(0x42424733)) {
            if (background_view) UnmapViewOfFile(background_view);
            CloseHandle(background_mapping);
            background_view = NULL; background_mapping = NULL;
        }
    }
    __atomic_store_n(&background_ready, 1, __ATOMIC_RELEASE);
    return TRUE;
}
#endif

uint64_t runtime_background_paused_ns(void) {
#ifdef _WIN32
    if (!__atomic_load_n(&background_ready, __ATOMIC_ACQUIRE))
        InitOnceExecuteOnce(&background_once, background_open, NULL, NULL);
    if (background_view)
        return __atomic_load_n((const uint64_t *)(background_view + 2), __ATOMIC_ACQUIRE);
#endif
    return 0;
}
