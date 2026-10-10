/* SPDX-License-Identifier: GPL-2.0-or-later
 * Executes the real runtime's generated x86-64 trampolines against a synthetic
 * game image. No Bloodborne executable or GPU is needed. */
#define _GNU_SOURCE
#include <assert.h>
#include <stdatomic.h>
#include <stdlib.h>
#ifndef _WIN32
#include <sys/mman.h>
#endif
#include "../src/runtime_cheats.c"

static _Atomic uint32_t mask;
static BbCheatOptions selected = {1,1,1,1.0f,0,0};
static uint32_t support;
const void *bbgpu_cheat_mask_address(void) { return &mask; }
__attribute__((noinline)) void bbgpu_cheat_options(BbCheatOptions *out) {
    *out = selected;
    /* Deliberately exercise volatile vector registers and the full x87/MXCSR
     * snapshot. A real game virtual call is also allowed to change this state. */
    const uint32_t alternate_mxcsr=0x9fc0;
    __asm__ volatile("vzeroall; ldmxcsr %0; fld1; fldpi; faddp" : : "m"(alternate_mxcsr) :
        "xmm0","xmm1","xmm2","xmm3","xmm4","xmm5","xmm6","xmm7",
        "xmm8","xmm9","xmm10","xmm11","xmm12","xmm13","xmm14","xmm15");
}
void bbgpu_cheat_support(uint32_t value) { support = value; }
void *runtime_low_map(size_t size, int prot) {
#ifdef _WIN32
    static uintptr_t next = 0x10000000;
    for (; next < 0x70000000; next += 0x10000) {
        void *p = VirtualAlloc((void *)next, size, MEM_RESERVE|MEM_COMMIT, PAGE_EXECUTE_READWRITE);
        if (p) { next += (size + 0xffff) & ~(size_t)0xffff; return p; }
    }
    return NULL;
#else
    return mmap(NULL,size,prot,MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);
#endif
}
extern ABI int invoke_cheat_fixture(const Registers *input, void *code,
                                unsigned char *ymm_state, Registers *output);
static const size_t image_size = 0x554f000;
static unsigned char *fixture(void) {
    unsigned char *image = runtime_low_map(image_size,PROT_READ|PROT_WRITE|PROT_EXEC);
    assert(image && image != (void *)-1);
    const unsigned char binding[] = {0x48,0x8b,0x47,0x08,0x48,0x8b,0x38,0x48,0x8b,0x07,0xff,0xa0,0x20,0x01,0,0};
    memcpy(image+0x125b700,binding,sizeof(binding));
    const unsigned char actual_player_check[] = {0x55,0x48,0x89,0xe5,0x41,0x56,0x53,0x48,0x89,0xfb,0x4c,0x8d,0x35,0x67,0xbb,0xc7,0x03};
    const unsigned char actual_player_compare[] = {0x48,0x39,0x58,0x60,0x0f,0x94,0xc0};
    memcpy(image+0x18c2d00,actual_player_check,sizeof(actual_player_check));
    memcpy(image+0x18c2d3d,actual_player_compare,sizeof(actual_player_compare));
    const unsigned char player_test[] = {0xcc,0xcc,0xcc,0xcc,0xcc}; // Calling the old slot must fail.
    memcpy(image+0x100,player_test,sizeof(player_test));
    uintptr_t method=(uintptr_t)image+0x100;
    memcpy(image+0x1000+0x120,&method,8);
    for (size_t i=0; i<sizeof(hooks)/sizeof(hooks[0]); ++i) {
        memcpy(image+hooks[i].offset,hooks[i].original,hooks[i].length);
        image[hooks[i].offset+hooks[i].length]=0xc3;
    }
    return image;
}
static void put_pointer(void *data, size_t offset, const void *value) {
    const uintptr_t p=(uintptr_t)value; memcpy((unsigned char *)data+offset,&p,8);
}
static void put_int(void *data, size_t offset, int value) { memcpy((unsigned char *)data+offset,&value,4); }
static int get_int(const void *data,size_t offset) { int value; memcpy(&value,(const unsigned char *)data+offset,4); return value; }
static float get_float(const void *data) { float v; memcpy(&v,data,4); return v; }
static void seed(unsigned char *state) {
    for (int i=0; i<128; ++i) { float v=0.25f+i; memcpy(state+4*i,&v,4); }
}
static void run(const Registers *input, void *code, Registers *out, unsigned char *state) {
    seed(state);
    _Alignas(16) unsigned char before[512]={0}, after[512]={0};
    __asm__ volatile("fxsave64 %0" : "=m"(before));
    assert(invoke_cheat_fixture(input,code,state,out)); /* SysV red zone survived. */
    __asm__ volatile("fxsave64 %0" : "=m"(after));
    assert(!memcmp(before,after,160)); /* x87 state and MXCSR survive the host callback. */
}
#ifdef TEST_WINDOWS_OBJECT
#include "coff_cheat_runtime.h"
#endif
int main(int argc, char **argv) {
#ifdef TEST_WINDOWS_OBJECT
    assert(argc>2);load_windows_runtime(argv[2]);
#endif
    if (argc > 1) {
        FILE *file=fopen(argv[1],"rb"); assert(file);
        for (size_t i=0; i<sizeof(hooks)/sizeof(hooks[0]); ++i) {
            unsigned char bytes[12];
            assert(!fseek(file,(long)hooks[i].offset,SEEK_SET));
            assert(fread(bytes,1,hooks[i].length,file)==hooks[i].length);
            assert(!memcmp(bytes,hooks[i].original,hooks[i].length));
        }
        const unsigned char player_start[] = {0x55,0x48,0x89,0xe5,0x41,0x56,0x53,0x48,0x89,0xfb,0x4c,0x8d,0x35,0x67,0xbb,0xc7,0x03};
        const unsigned char player_compare[] = {0x48,0x39,0x58,0x60,0x0f,0x94,0xc0};
        unsigned char bytes[17];
        assert(!fseek(file,0x18c2d00,SEEK_SET) && fread(bytes,1,17,file)==17);
        assert(!memcmp(bytes,player_start,17));
        int32_t displacement;memcpy(&displacement,bytes+13,4);
        assert(0x18c2d11+displacement==WORLD_CHR_MAN);
        assert(!fseek(file,0x18c2d3d,SEEK_SET) && fread(bytes,1,7,file)==7);
        assert(!memcmp(bytes,player_compare,7));
        fclose(file); puts("PASS: ten hook signatures and the actual WorldChrMan/mainPlayer lookup match the supplied 1.09 image.");
    }
    unsigned char *image=fixture();
#ifdef TEST_WINDOWS_OBJECT
    /* Extra direct helper assertions use the native copy of the same source;
     * every installed hook/handler is the Windows compiler's actual object. */
    game_begin=(uintptr_t)image;game_end=game_begin+image_size;
#endif
    unsigned char actor[64]={0}, enemy[64]={0}, component[0x400]={0}, victim[0x400]={0};
    unsigned char table[0x40]={0}, hit[0x240]={0}, frame[0x400]={0}, data[0x100]={0};
    unsigned char world[0x68]={0};
    put_pointer(image,WORLD_CHR_MAN,world); put_pointer(world,0x60,actor);
    put_pointer(actor,0,image+0x1000); actor[0x10]=1;
    put_pointer(enemy,0,image+0x1000);
    put_pointer(component,8,actor); put_pointer(victim,8,enemy);
    put_pointer(table,0x20,victim); put_pointer(frame,0xe8,actor); /* rbp-0x318 */
    put_int(hit,0x22c,100); put_int(data,0x94,100);
    const float speed=1.25f; memcpy(component+0x374,&speed,4);
    Registers input[10], baseline[10], result;
    unsigned char baseline_ymm[10][512], state[512];
    for (unsigned i=0; i<10; ++i) {
        uint64_t *registers=(uint64_t *)&input[i];
        for (unsigned n=0; n<15; ++n) registers[n]=0x11001100u+n;
        input[i].flags=0x247;
        switch (i) {
        case 0: input[i].rax=(uintptr_t)table; input[i].rcx=(uintptr_t)hit; input[i].rbp=(uintptr_t)frame+0x400; break;
        case 1: input[i].rdx=(uintptr_t)data; input[i].rbx=100; input[i].r14=(uintptr_t)actor; break;
        case 2: input[i].rax=(uintptr_t)data; input[i].rdi=100; break;
        case 3: input[i].r13=(uintptr_t)component; break;
        case 4: input[i].r14=(uintptr_t)component; break;
        case 5: input[i].r12=(uintptr_t)component; break;
        case 6: input[i].rbx=(uintptr_t)component; break;
        case 7: input[i].rdx=(uintptr_t)component; input[i].rbx=(uintptr_t)actor; break;
        case 8: input[i].rax=(uintptr_t)component; input[i].rbx=(uintptr_t)actor; break;
        case 9: input[i].r14=2; input[i].rbx=(uintptr_t)actor; break;
        }
        run(&input[i],image+hooks[i].offset,&baseline[i],baseline_ymm[i]);
    }
    assert(runtime_cheats_install(image,image_size,"01.08")==0 && support==0);
    assert(memcmp(image+hooks[0].offset,hooks[0].original,hooks[0].length)==0);
    assert(runtime_cheats_install(image,image_size,"01.09")==BB_CHEAT_ALL && support==BB_CHEAT_ALL);
    /* Off is identical to executing the untouched game instruction, including
     * flags, every GPR, every YMM lane and the game's red zone. */
    for (unsigned i=0; i<10; ++i) {
        atomic_store(&mask,0);
        run(&input[i],image+hooks[i].offset,&result,state);
        assert(!memcmp(&result,&baseline[i],sizeof(result)));
        assert(!memcmp(state,baseline_ymm[i],512));
    }
    /* Real host callbacks must preserve everything they do not intentionally edit. */
    for (unsigned i=0; i<10; ++i) {
        atomic_store(&mask,hooks[i].group);
        selected=(BbCheatOptions){1,1,1,1.0f,1,1};
        run(&input[i],image+hooks[i].offset,&result,state);
        Registers expected=baseline[i];
        if (i>=4 && i<=6) test_nonzero(&expected,0x80);
        if (i==7) expected.rdx|=0x200;
        if (i==8) test_nonzero(&expected,2);
        if (i==9) { expected.r14=0; expected.rcx=0; expected.flags=(expected.flags&~UINT64_C(0x8d5))|0x44; }
        assert(!memcmp(&result,&expected,sizeof(result)));
        if (memcmp(state,baseline_ymm[i],512)) {
            for (unsigned byte=0;byte<512;++byte) if (state[byte]!=baseline_ymm[i][byte]) {
                fprintf(stderr,"YMM mismatch at hook %u, byte %u: %02x expected %02x\n",i,byte,state[byte],baseline_ymm[i][byte]); break;
            }
        }
        assert(!memcmp(state,baseline_ymm[i],512));
    }
    for (unsigned factor=2; factor<=16; factor*=2) {
        selected.damage=factor; selected.incoming=factor; selected.echoes=factor;
        atomic_store(&mask,BB_CHEAT_ALL);
        put_pointer(frame,0xe8,actor); put_pointer(table,0x20,victim); put_int(hit,0x22c,100);
        run(&input[0],image+hooks[0].offset,&result,state);
        assert(result.r12==100*factor && get_int(hit,0x22c)==100*(int)factor);
        put_pointer(frame,0xe8,enemy); put_pointer(table,0x20,component); put_int(hit,0x22c,100);
        run(&input[0],image+hooks[0].offset,&result,state);
        assert(result.r12==100/factor && get_int(hit,0x22c)==100/(int)factor);
        put_pointer(table,0x20,victim); put_int(hit,0x22c,100);
        run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==100); /* Enemy vs enemy. */
        run(&input[1],image+hooks[1].offset,&result,state); assert(result.rbx==100*factor);
        run(&input[2],image+hooks[2].offset,&result,state); assert(result.rdi==100+100*factor);
    }
    put_pointer(frame,0xe8,actor); put_int(hit,0x22c,INT_MAX);
    run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==INT_MAX);
    put_int(hit,0x22c,0); run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==0);
    put_int(hit,0x22c,-100); run(&input[0],image+hooks[0].offset,&result,state); assert((int)result.r12==-100);
    put_pointer(frame,0xe8,NULL); put_pointer(table,0x20,component); put_int(hit,0x22c,100);
    run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==100); /* Environment. */
    put_pointer(frame,0xe8,actor);
    run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==100); /* Self damage. */
    put_pointer(frame,0xe8,enemy); put_int(hit,0x22c,1);
    run(&input[0],image+hooks[0].offset,&result,state); assert(result.r12==1);
    input[1].rbx=INT_MAX; input[2].rdi=INT_MAX; put_int(data,0x94,999999990);
    run(&input[1],image+hooks[1].offset,&result,state); assert(result.rbx==9);
    run(&input[2],image+hooks[2].offset,&result,state); assert(result.rdi==999999999);
    input[1].rbx=(uint32_t)-5; input[2].rdi=(uint32_t)-5; put_int(data,0x94,100);
    run(&input[1],image+hooks[1].offset,&result,state); assert((int)result.rbx==-5);
    run(&input[2],image+hooks[2].offset,&result,state); assert(result.rdi==95); /* No multiplier on costs. */
    for (float factor=1.5f; factor<=16.0f; factor=factor==1.5f ? 2.0f : factor*2.0f) {
        selected.movement=factor;
        run(&input[3],image+hooks[3].offset,&result,state); assert(get_float(state)==speed*factor);
        assert(get_float(component+0x374)==speed);
    }
    /* Player guards leave NPC stamina, movement and consumables unchanged. */
    put_pointer(component,8,enemy); input[7].rbx=(uintptr_t)enemy; input[8].rbx=(uintptr_t)enemy; input[9].rbx=(uintptr_t)enemy;
    for (unsigned i=3; i<10; ++i) {
        run(&input[i],image+hooks[i].offset,&result,state);
        assert(!memcmp(&result,&baseline[i],sizeof(result)) || i>=7); /* Actor register changed in those inputs. */
        if (i>=7) { Registers expected=baseline[i]; expected.rbx=(uintptr_t)enemy; assert(!memcmp(&result,&expected,sizeof(result))); }
        assert(!memcmp(state,baseline_ymm[i],512));
    }
    /* The real WorldChrMan slot can be empty during startup/save loading. No
     * game virtual function is called, and all player-only handlers stay Off. */
    put_pointer(image,WORLD_CHR_MAN,NULL);
    assert(!local_player((uintptr_t)actor));
    assert(!local_player(0));
    assert(!local_player(0x12345678)); /* Never dereference the supplied actor. */
    put_pointer(component,8,actor);
    put_pointer(frame,0xe8,actor);put_pointer(table,0x20,victim);
    input[7].rbx=input[8].rbx=input[9].rbx=(uintptr_t)actor;
    for (int absent=0;absent<2;++absent) {
        if (absent) {put_pointer(image,WORLD_CHR_MAN,world);put_pointer(world,0x60,NULL);}
        for (unsigned i=0;i<10;++i) {
            if (i==2) continue; // Positive persistent-data awards have no actor lookup.
            Registers expected;unsigned char expected_state[512];
            atomic_store(&mask,0);run(&input[i],image+hooks[i].offset,&expected,expected_state);
            atomic_store(&mask,BB_CHEAT_ALL);run(&input[i],image+hooks[i].offset,&result,state);
            assert(!memcmp(&result,&expected,sizeof(result)));
            assert(!memcmp(state,expected_state,512));
        }
    }
    puts("PASS: enabled Windows-compatible hooks safely preserve original behavior with no world or no player during save loading.");
    put_pointer(image,WORLD_CHR_MAN,world);
    put_pointer(world,0x60,NULL); assert(!local_player((uintptr_t)actor));
    put_pointer(world,0x60,actor); assert(local_player((uintptr_t)actor));
    /* Slot 0x120 is deliberately unrelated; it must never be invoked. */
    memset(image+0x100,0xcc,5);
    assert(local_player((uintptr_t)actor));
    unsigned char *conflict=fixture(); conflict[hooks[8].offset]^=1;
    assert(runtime_cheats_install(conflict,image_size,"01.09")== (BB_CHEAT_ALL&~BB_CHEAT_CONSUMABLES));
    for (unsigned i=7; i<10; ++i) assert(conflict[hooks[i].offset]!=0xe9); /* Whole group disabled, never partial. */
#ifdef _WIN32
    VirtualFree(image,0,MEM_RELEASE); VirtualFree(conflict,0,MEM_RELEASE);
#else
    munmap(image,image_size); munmap(conflict,image_size);
#endif
    puts("PASS: guarded 1.09 hook installation; real trampoline execution; all damage, reduction, Echoes and movement multipliers; player-only stamina/item/ammunition paths; Off, NPCs, healing, environment and costs preserved; overflow limits; GPR/YMM/flags/red-zone preservation; patch conflicts disable the entire feature.");
}
