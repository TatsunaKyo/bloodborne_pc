/* SPDX-License-Identifier: GPL-2.0-or-later
 * The native pause gate leaves SDL responsive and accounts for guest-clock time. */
#include "runtime.h"
#include "../gpu/bbgpu.h"
uint64_t runtime_background_paused_ns(void) {
    return bbgpu_background_paused_ns();
}
