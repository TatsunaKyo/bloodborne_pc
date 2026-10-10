/* SPDX-License-Identifier: GPL-2.0-or-later
 * Run the actual MinGW runtime_cheats.c object on x86-64 Linux. Only its host
 * OS/CRT imports are replaced, using the Windows x64 ABI; guest handlers and
 * emitted trampolines execute unchanged. No Wine or game assets are needed. */
#include <stdarg.h>
#define HOST_WIN __attribute__((ms_abi))
static HOST_WIN int host_protect(void* p,size_t size,uint32_t protection,uint32_t* old) {
    (void)protection;*old=0;return mprotect(p,size,PROT_READ|PROT_EXEC)==0;
}
static HOST_WIN void* host_process(void) {return (void*)-1;}
static HOST_WIN int host_flush(void* process,const void* p,size_t size) {
    (void)process;__builtin___clear_cache((char*)p,(char*)p+size);return 1;
}
static HOST_WIN void host_options(BbCheatOptions* p) {bbgpu_cheat_options(p);}
static HOST_WIN void host_support(uint32_t value) {bbgpu_cheat_support(value);}
static HOST_WIN const void* host_mask(void) {return bbgpu_cheat_mask_address();}
static HOST_WIN void* host_map(size_t size,int prot) {return runtime_low_map(size,prot);}
static HOST_WIN void* host_memcpy(void* a,const void* b,size_t n) {return memcpy(a,b,n);}
static HOST_WIN int host_strcmp(const char* a,const char* b) {return strcmp(a,b);}
static HOST_WIN int host_puts(const char* text) {return puts(text);}
/* The runtime's diagnostic printf calls have one integer argument. */
static HOST_WIN int host_printf(const char* fmt,uintptr_t value) {return printf(fmt,value);}
static uintptr_t host_import(const char* name) {
    static void* protect=(void*)host_protect,*process=(void*)host_process,*flush=(void*)host_flush;
    const struct {const char* name;uintptr_t value;} imports[]={
        {"__imp_VirtualProtect",(uintptr_t)&protect},
        {"__imp_GetCurrentProcess",(uintptr_t)&process},
        {"__imp_FlushInstructionCache",(uintptr_t)&flush},
        {"bbgpu_cheat_options",(uintptr_t)host_options},
        {"bbgpu_cheat_support",(uintptr_t)host_support},
        {"bbgpu_cheat_mask_address",(uintptr_t)host_mask},
        {"runtime_low_map",(uintptr_t)host_map},
        {"memcpy",(uintptr_t)host_memcpy},{"strcmp",(uintptr_t)host_strcmp},
        {"puts",(uintptr_t)host_puts},{"__mingw_printf",(uintptr_t)host_printf}};
    for(size_t i=0;i<sizeof(imports)/sizeof(imports[0]);++i)
        if(!strcmp(name,imports[i].name))return imports[i].value;
    fprintf(stderr,"Unknown Windows COFF import: %s\n",name);abort();
}
static uint16_t coff16(const unsigned char* p) {uint16_t v;memcpy(&v,p,2);return v;}
static uint32_t coff32(const unsigned char* p) {uint32_t v;memcpy(&v,p,4);return v;}
typedef uint32_t (HOST_WIN *WindowsInstaller)(void*,size_t,const char*);
static WindowsInstaller windows_installer;
static void load_windows_runtime(const char* file) {
    FILE* f=fopen(file,"rb");assert(f);fseek(f,0,SEEK_END);const long length=ftell(f);rewind(f);
    unsigned char* data=malloc((size_t)length);assert(fread(data,1,(size_t)length,f)==(size_t)length);fclose(f);
    assert(coff16(data)==0x8664 && coff16(data+16)==0);
    const unsigned nsections=coff16(data+2),nsymbols=coff32(data+12),symoff=coff32(data+8);
    assert(nsections<128 && symoff+nsymbols*18+4<=(unsigned long)length);
    uintptr_t sections[128]={0};
    unsigned char* code=mmap(NULL,1024*1024,PROT_READ|PROT_WRITE|PROT_EXEC,
        MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);assert(code!=MAP_FAILED);
    size_t offset=0;
    for(unsigned i=0;i<nsections;++i) {
        const unsigned char* s=data+20+i*40;const unsigned size=coff32(s+16),raw=coff32(s+20);
        sections[i]=(uintptr_t)code+offset;
        assert(offset+size<1024*1024 && (!raw || raw+size<=(unsigned long)length));
        if(raw && size)memcpy((void*)sections[i],data+raw,size);
        offset+=(size+4095)&~(size_t)4095;if(!size)offset+=4096;
    }
    uintptr_t* symbols=calloc(nsymbols,sizeof(uintptr_t));assert(symbols);
    const char* strings=(const char*)data+symoff+nsymbols*18;
    for(unsigned i=0;i<nsymbols;) {
        const unsigned char* s=data+symoff+i*18;
        char short_name[9]={0};memcpy(short_name,s,8);
        const char* name=coff32(s) ? short_name : strings+coff32(s+4);
        const int16_t section=(int16_t)coff16(s+12);const unsigned value=coff32(s+8);
        if(section>0) {assert((unsigned)section<=nsections);symbols[i]=sections[section-1]+value;}
        else if(section==-1)symbols[i]=value;
        else if(section==0 && s[16]==2)symbols[i]=host_import(name);
        if(!strcmp(name,"runtime_cheats_install"))windows_installer=(WindowsInstaller)symbols[i];
        i+=1+s[17];
    }
    for(unsigned i=0;i<nsections;++i) {
        const unsigned char* s=data+20+i*40;const unsigned rel=coff32(s+24),count=coff16(s+32);
        assert(rel+count*10<=(unsigned long)length);
        for(unsigned j=0;j<count;++j) {
            const unsigned char* r=data+rel+j*10;const unsigned sym=coff32(r+4),type=coff16(r+8);
            unsigned char* site=(unsigned char*)sections[i]+coff32(r);assert(sym<nsymbols);
            const uintptr_t target=symbols[sym];assert(target);
            if(type==1) {uint64_t v;memcpy(&v,site,8);v+=target;memcpy(site,&v,8);}
            else if(type>=4 && type<=9) {
                int32_t addend;memcpy(&addend,site,4);
                const int64_t delta=(int64_t)target-(int64_t)(uintptr_t)(site+4)-(type-4)+addend;
                assert(delta>=INT32_MIN && delta<=INT32_MAX);const int32_t v=(int32_t)delta;memcpy(site,&v,4);
            } else if(type==3) {uint32_t v=coff32(site)+(uint32_t)(target-(uintptr_t)code);memcpy(site,&v,4);}
            else {fprintf(stderr,"Unsupported COFF relocation %u\n",type);abort();}
        }
    }
    assert(windows_installer);free(symbols);free(data);
    puts("Executing the actual Windows runtime object with Windows x64 host ABI imports.");
}
#define runtime_cheats_install windows_installer
