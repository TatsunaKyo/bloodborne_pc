/* SPDX-License-Identifier: GPL-2.0-or-later
 * TatsunaKyo revision: opt-in, player-only cheats for the verified 1.09 executable.
 * Off takes a single atomic mask test, with no host callback or player lookup.
 * No game executable, trainer or fixed-address code cave is distributed here. */
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#include "runtime.h"
#include "../gpu/bbcheats.h"
#include <limits.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

typedef struct {
    uint64_t r15, r14, r13, r12, r11, r10, r9, r8;
    uint64_t rdi, rsi, rbp, rbx, rdx, rcx, rax, flags;
} Registers;
typedef void (ABI *Handler)(Registers *, unsigned char *);
static uintptr_t game_begin, game_end;
/* ChrIns::IsLocalPlayer (1.09, image 0x18c2d00) compares this with
 * WorldChrMan::mainPlayer at +0x60. The script binding's vtable belongs to a
 * different object; calling ChrIns slot 0x120 executes an unrelated update. */
enum { WORLD_CHR_MAN = 0x553e878 };

static uintptr_t pointer(uintptr_t address) {
    uintptr_t result;
    memcpy(&result, (const void *)address, sizeof(result));
    return result;
}
static int in_image(uintptr_t address, size_t size) {
    return address >= game_begin && address < game_end && size <= game_end - address;
}
static int local_player(uintptr_t actor) {
    if (actor < 65536) return 0;
    if (!in_image(game_begin + WORLD_CHR_MAN, sizeof(uintptr_t))) return 0;
    const uintptr_t world = pointer(game_begin + WORLD_CHR_MAN);
    /* Unlike the game's assertion path, loading/unloading simply means Off. */
    return world >= 65536 && actor == pointer(world + 0x60);
}
static int component_is_player(uintptr_t component) {
    return component >= 65536 && local_player(pointer(component + 8));
}

static ABI void damage(Registers *r, unsigned char *fpu) {
    (void)fpu;
    const int original = (int)(uint32_t)r->r12;
    if (original <= 0) return; /* Healing and immune hits keep the game's result. */
    BbCheatOptions options; bbgpu_cheat_options(&options);
    const uintptr_t attacker = pointer(r->rbp - 0x318);
    const uintptr_t victim_stats = pointer(r->rax + 0x20);
    const int player_attacker = local_player(attacker);
    const int player_victim = component_is_player(victim_stats);
    uint64_t result = (unsigned)original;
    if (player_attacker && !player_victim) result *= options.damage;
    else if (attacker && !player_attacker && player_victim) {
        /* Only enemy hits: fall damage and environmental HP setters are untouched. */
        result /= options.incoming;
        if (!result) result = 1;
    }
    if (result > INT_MAX) result = INT_MAX;
    r->r12 = (uint32_t)result;
    /* HP loss, rally bookkeeping and displayed damage must agree. */
    const uint32_t applied = (uint32_t)result;
    memcpy((void *)(r->rcx + 0x22c), &applied, sizeof(applied));
}
static uint32_t award(int gain, int balance, unsigned multiplier) {
    if (gain <= 0) return (uint32_t)gain;
    const uint64_t limit = 999999999u;
    const uint64_t current = balance > 0 ? (unsigned)balance : 0u;
    const uint64_t room = current >= limit ? 0u : limit - current;
    const uint64_t scaled = (uint64_t)(unsigned)gain * multiplier;
    return (uint32_t)(scaled < room ? scaled : room);
}
static ABI void echoes_actor(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (!local_player(r->r14)) return;
    BbCheatOptions options; bbgpu_cheat_options(&options);
    r->rbx = award((int)(uint32_t)r->rbx, (int)(uint32_t)r->rax, options.echoes);
}
static ABI void echoes_data(Registers *r, unsigned char *fpu) {
    (void)fpu;
    int balance; memcpy(&balance, (const void *)(r->rax + 0x94), sizeof(balance));
    BbCheatOptions options; bbgpu_cheat_options(&options);
    r->rdi = award((int)(uint32_t)r->rdi, balance, options.echoes);
}
static ABI void movement(Registers *r, unsigned char *fpu) {
    if (!component_is_player(r->r13)) return;
    BbCheatOptions options; bbgpu_cheat_options(&options);
    /* The saved YMM0 slot, not the persistent motion component or animations. */
    float speed; memcpy(&speed, fpu + 512, sizeof(speed));
    if (!isfinite(speed)) return;
    speed *= options.movement;
    if (isfinite(speed)) memcpy(fpu + 512, &speed, sizeof(speed));
}
static void test_nonzero(Registers *r, unsigned char value) {
    /* TEST clears CF/OF and sets SF/ZF/PF; these engine branches test bit 7 or bit 1. */
    r->flags &= ~UINT64_C(0x8c5);
    if (value & 0x80) r->flags |= 0x80;
}
static ABI void stamina_general(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (component_is_player(r->r14)) test_nonzero(r, 0x80);
}
static ABI void stamina_guard(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (component_is_player(r->r12)) test_nonzero(r, 0x80);
}
static ABI void stamina_guard_overmax(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (component_is_player(r->rbx)) test_nonzero(r, 0x80);
}
static ABI void item_use(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (local_player(r->rbx)) r->rdx |= 0x200;
}
static ABI void ammunition_use(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (local_player(r->rbx)) test_nonzero(r, 2);
}
static ABI void equipped_ammunition_use(Registers *r, unsigned char *fpu) {
    (void)fpu;
    if (local_player(r->rbx) && (int)(uint32_t)r->r14 > 0) r->r14 = 0;
}

typedef struct {
    size_t offset;
    unsigned char original[12];
    unsigned char length, before;
    uint32_t group;
    Handler handler;
} Hook;
static const Hook hooks[] = {
    {0x1a2bec1, {0x44,0x8b,0xa1,0x2c,0x02,0,0}, 7,0, BB_CHEAT_DAMAGE|BB_CHEAT_INCOMING, damage},
    {0x190027f, {0x8b,0x82,0x94,0,0,0}, 6,0, BB_CHEAT_ECHOES, echoes_actor},
    {0x1b63b95, {0x03,0xb8,0x94,0,0,0}, 6,1, BB_CHEAT_ECHOES, echoes_data},
    {0x1a196bb, {0xc4,0xc1,0x7a,0x10,0x85,0x74,0x03,0,0}, 9,0, BB_CHEAT_MOVEMENT, movement},
    {0x1a571a7, {0x41,0xf6,0x86,0,0x02,0,0,0x80}, 8,0, BB_CHEAT_STAMINA, stamina_general},
    {0x1a2c265, {0x41,0xf6,0x84,0x24,0,0x02,0,0,0x80}, 9,0, BB_CHEAT_STAMINA, stamina_guard},
    {0x1a2c355, {0xf6,0x83,0,0x02,0,0,0x80}, 7,0, BB_CHEAT_STAMINA, stamina_guard_overmax},
    {0x18f9814, {0x0f,0xb7,0x92,0,0x02,0,0}, 7,0, BB_CHEAT_CONSUMABLES, item_use},
    {0x18f9f31, {0xf6,0x80,0x01,0x02,0,0,0x02}, 7,0, BB_CHEAT_CONSUMABLES, ammunition_use},
    {0x18fa57d, {0x41,0xf7,0xde,0x31,0xc9}, 5,1, BB_CHEAT_CONSUMABLES, equipped_ammunition_use},
};

typedef struct { unsigned char *start, *next; } Emitter;
static void bytes(Emitter *e, const void *data, size_t size) {
    memcpy(e->next, data, size); e->next += size;
}
#define EMIT(e, ...) do { const unsigned char b[] = {__VA_ARGS__}; bytes(e,b,sizeof(b)); } while (0)
static int rel32(unsigned char *operand, uintptr_t target) {
    const int64_t delta = (int64_t)target - (int64_t)(uintptr_t)(operand + 4);
    if (delta < INT32_MIN || delta > INT32_MAX) return 0;
    const int32_t value = (int32_t)delta; memcpy(operand, &value, 4); return 1;
}
static void leave_fast_gate(Emitter *e) {
    EMIT(e, 0x58,0x9d, 0x48,0x8d,0xa4,0x24,0x80,0,0,0); /* pop rax; popfq; lea rsp,[rsp+128] */
}
static void ymm(Emitter *e, int load) {
    for (unsigned reg = 0; reg < 16; ++reg) {
        EMIT(e, 0xc5,reg < 8 ? 0xfe : 0x7e,load ? 0x6f : 0x7f,0x84|((reg&7)<<3),0x24);
        const uint32_t offset = 512 + reg * 32; bytes(e,&offset,4);
    }
}
static int trampoline(Emitter *e, const Hook *hook, uintptr_t return_address, const void *mask) {
    if (!hook->before) bytes(e, hook->original, hook->length);
    EMIT(e, 0x48,0x8d,0xa4,0x24,0x80,0xff,0xff,0xff, 0x9c,0x50, 0x48,0xb8);
    const uintptr_t mask_address = (uintptr_t)mask; bytes(e,&mask_address,8);
    EMIT(e, 0xf7,0x00); bytes(e,&hook->group,4); /* test dword [rax],group */
    EMIT(e, 0x0f,0x84); unsigned char *skip = e->next; EMIT(e,0,0,0,0);
    leave_fast_gate(e);
    /* Save all live state below the SysV red zone. RBX is the callee-saved snapshot pointer. */
    EMIT(e, 0x48,0x8d,0xa4,0x24,0x80,0xff,0xff,0xff, 0x9c,
         0x50,0x51,0x52,0x53,0x55,0x56,0x57,
         0x41,0x50,0x41,0x51,0x41,0x52,0x41,0x53,0x41,0x54,0x41,0x55,0x41,0x56,0x41,0x57,
         0x48,0x89,0xe3, /* mov rbx,rsp */
         0x48,0x81,0xec,0x40,0x04,0,0, 0x48,0x83,0xe4,0xc0, /* reserve 1088; align 64 */
         0x48,0x0f,0xae,0x04,0x24); /* fxsave64 [rsp] */
    ymm(e,0);
    EMIT(e, 0x48,0x89,0xdf,0x48,0x89,0xe6,0x48,0xb8); /* SysV rdi=snapshot,rsi=FPU */
    const uintptr_t handler = (uintptr_t)hook->handler; bytes(e,&handler,8);
    EMIT(e, 0xff,0xd0, 0x48,0x0f,0xae,0x0c,0x24); /* call; fxrstor64 */
    ymm(e,1);
    EMIT(e, 0x48,0x89,0xdc,
         0x41,0x5f,0x41,0x5e,0x41,0x5d,0x41,0x5c,0x41,0x5b,0x41,0x5a,0x41,0x59,0x41,0x58,
         0x5f,0x5e,0x5d,0x5b,0x5a,0x59,0x58,0x9d, 0x48,0x8d,0xa4,0x24,0x80,0,0,0);
    EMIT(e, 0xe9); unsigned char *done = e->next; EMIT(e,0,0,0,0);
    if (!rel32(skip,(uintptr_t)e->next)) return 0;
    leave_fast_gate(e);
    if (!rel32(done,(uintptr_t)e->next)) return 0;
    if (hook->before) bytes(e, hook->original, hook->length);
    EMIT(e, 0xe9); unsigned char *back = e->next; EMIT(e,0,0,0,0);
    return rel32(back,return_address);
}

uint32_t runtime_cheats_install(void *image, size_t size, const char *app_version) {
    const unsigned char player_binding[] = {0x48,0x8b,0x47,0x08,0x48,0x8b,0x38,0x48,0x8b,0x07,
                                            0xff,0xa0,0x20,0x01,0,0};
    bbgpu_cheat_support(0);
    const unsigned char local_player_start[] = {0x55,0x48,0x89,0xe5,0x41,0x56,0x53,
        0x48,0x89,0xfb,0x4c,0x8d,0x35,0x67,0xbb,0xc7,0x03};
    const unsigned char local_player_compare[] = {0x48,0x39,0x58,0x60,0x0f,0x94,0xc0};
    if (!app_version || strcmp(app_version,"01.09") || size < WORLD_CHR_MAN + 8 ||
        memcmp((unsigned char *)image+0x125b700,player_binding,sizeof(player_binding)) ||
        memcmp((unsigned char *)image+0x18c2d00,local_player_start,sizeof(local_player_start)) ||
        memcmp((unsigned char *)image+0x18c2d3d,local_player_compare,sizeof(local_player_compare))) {
        puts("Live cheats: executable/version guard failed; no hooks installed"); return 0;
    }
    uint32_t supported = BB_CHEAT_ALL;
    for (size_t i=0; i<sizeof(hooks)/sizeof(hooks[0]); ++i) {
        const Hook *hook=&hooks[i];
        if (hook->offset > size || hook->length > size-hook->offset ||
            memcmp((unsigned char *)image+hook->offset,hook->original,hook->length)) {
            supported &= ~hook->group;
            printf("Live cheats: signature mismatch at image offset 0x%zx; group disabled\n",hook->offset);
        }
    }
    if (!supported) return 0;
    const size_t capacity = 16384;
    unsigned char *code = runtime_low_map(capacity,PROT_READ|PROT_WRITE);
    if (!code || code == (void *)-1) return 0;
    Emitter e={code,code};
    unsigned char *destinations[sizeof(hooks)/sizeof(hooks[0])] = {0};
    const void *mask = bbgpu_cheat_mask_address();
    for (size_t i=0; i<sizeof(hooks)/sizeof(hooks[0]); ++i) {
        const Hook *hook=&hooks[i];
        if (!(hook->group & supported)) continue;
        destinations[i]=e.next;
        if (!trampoline(&e,hook,(uintptr_t)image+hook->offset+hook->length,mask)) return 0;
        /* Maximum generated size per hook is below 768 bytes. */
        if ((size_t)(e.next-code)+768 > capacity) return 0;
        const int64_t distance = (int64_t)(uintptr_t)destinations[i] -
            (int64_t)((uintptr_t)image + hook->offset + 5);
        if (distance < INT32_MIN || distance > INT32_MAX) return 0;
    }
#ifdef _WIN32
    DWORD old;
    if (!VirtualProtect(code,capacity,PAGE_EXECUTE_READ,&old)) return 0;
    FlushInstructionCache(GetCurrentProcess(),code,capacity);
#else
    if (mprotect(code,capacity,PROT_READ|PROT_EXEC)) return 0;
    __builtin___clear_cache((char *)code,(char *)e.next);
#endif
    game_begin=(uintptr_t)image; game_end=game_begin+size;
    for (size_t i=0; i<sizeof(hooks)/sizeof(hooks[0]); ++i) {
        if (!destinations[i]) continue;
        const Hook *hook=&hooks[i];
        unsigned char *site=(unsigned char *)image+hook->offset;
        site[0]=0xe9;
        /* Range was checked before any game bytes were modified. */
        (void)rel32(site+1,(uintptr_t)destinations[i]);
        memset(site+5,0x90,hook->length-5);
    }
    bbgpu_cheat_support(supported);
    printf("Live cheats: verified 1.09 hooks installed, support mask 0x%02x\n",supported);
    return supported;
}
