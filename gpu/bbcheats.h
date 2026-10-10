/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef BBCHEATS_H
#define BBCHEATS_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
enum {
    BB_CHEAT_DAMAGE = 1u, BB_CHEAT_INCOMING = 2u, BB_CHEAT_ECHOES = 4u,
    BB_CHEAT_MOVEMENT = 8u, BB_CHEAT_STAMINA = 16u, BB_CHEAT_CONSUMABLES = 32u,
    BB_CHEAT_ALL = 63u
};
typedef struct {
    unsigned damage, incoming, echoes;
    float movement;
    int stamina, consumables;
} BbCheatOptions;
/* Machine-code trampolines read one aligned, lock-free 32-bit atomic before saving
 * registers. Disabled cheats never call into the host or the game's player test. */
const void *bbgpu_cheat_mask_address(void);
void bbgpu_cheat_options(BbCheatOptions *options);
void bbgpu_cheat_support(uint32_t mask);
/* Installed before guest threads start, only on the verified Bloodborne 1.09 image. */
uint32_t runtime_cheats_install(void *image, size_t size, const char *app_version);
#ifdef __cplusplus
}
#endif
#endif
