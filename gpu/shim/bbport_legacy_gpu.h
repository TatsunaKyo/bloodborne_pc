/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stdint.h>
#include <string.h>
/* Evaluate the REAL selected adapter before a mod can spoof any capability. */
static inline int bb_dlssg_mod_gpu(uint32_t vendor, const char *name) {
    if (vendor != 0x10de || !name) return 0;
    const char *p = strstr(name, "GeForce RTX ");
    if (!p) return 0;
    p += 12;
    return (p[0]=='2' || p[0]=='3') && p[1]=='0' &&
           p[2]>='0' && p[2]<='9' && p[3]>='0' && p[3]<='9' &&
           (p[4]=='\0' || p[4]==' ');
}
