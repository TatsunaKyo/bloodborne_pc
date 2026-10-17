/* Exercise actual guest file operations on a linked overlay and writable saves. */
#include "../src/runtime_file.c"
void runtime_memory_prepare_io_write(uintptr_t address,uint64_t size) {(void)address;(void)size;}
#include <assert.h>
#include <sys/wait.h>
void runtime_quit_on_open(const char *guest) {(void)guest;}
static int32_t guest_errno;
int32_t *runtime_errno(void) { return &guest_errno; }
int32_t runtime_guest_errno(int e) { return e; }
uintptr_t runtime_lookup(const RuntimeExport *table,size_t n,const char *name) {
    for (size_t i=0;i<n;++i) if (!strcmp(table[i].name,name)) return (uintptr_t)table[i].function;
    return 0;
}
int main(void) {
    char root[]="/tmp/bbport-mod-files-XXXXXX";
    assert(mkdtemp(root));
    char game[512],user[512],source[512],link[512];
    snprintf(game,sizeof(game),"%s/game",root);
    snprintf(user,sizeof(user),"%s/user",root);
    snprintf(source,sizeof(source),"%s/mod.dcx",root);
    snprintf(link,sizeof(link),"%s/game/asset.dcx",root);
    assert(!mkdir(game,0755));
    FILE *f=fopen(source,"w"); assert(f); assert(fputs("modded",f)>=0); assert(!fclose(f));
    assert(!symlink(source,link));
    runtime_file_configure(game,user);
    for (int i=0;i<3;++i) {
        const char *path=i==0 ? "/app0/asset.dcx" : i==1 ? "/hostapp/asset.dcx" : "asset.dcx";
        int fd=(int)do_open(path,0,0); assert(fd>=3);
        char content[8]={0}; assert(do_read(fd,content,6)==6 && !strcmp(content,"modded"));
        GuestStat info; assert(!do_stat(path,&info) && info.size==6);
        assert(!do_close(fd));
        assert(do_open(path,2,0)==-EROFS);
        assert(do_open(path,0x400,0)==-EROFS);
        assert(do_truncate(path,0)==-EROFS);
        assert(path_op(path,2,0)==-EROFS);
        assert(do_rename(path,"/data/moved")==-EROFS);
    }
    int dir=(int)do_open("/app0",0x20000,0); assert(dir>=3);
    char entries[1024]; int64_t count=do_getdents(dir,entries,sizeof(entries),NULL); assert(count>0);
    int found=0;
    for (int64_t p=0;p<count;) {
        uint16_t length; memcpy(&length,entries+p+4,2);
        assert(length);
        if (!strcmp(entries+p+8,"asset.dcx")) { assert(entries[p+6]==8); found=1; }
        p+=length;
    }
    assert(found && !do_close(dir));
    int save=(int)do_open("/data/test-save",0x202,0644); assert(save>=3);
    assert(do_write(save,"save",4)==4 && !do_close(save));
    assert(!path_op("/data/test-save",2,0));
    char savedir[512],state[1024];snprintf(savedir,sizeof(savedir),"%s/savedata",root);
    assert(!mkdir(savedir,0755));snprintf(state,sizeof(state),"%s/state",savedir);
    assert(!runtime_file_mount("/savedata0",savedir));
    FILE *seed=fopen(state,"wb");assert(seed);assert(fwrite("old-safe",1,8,seed)==8);assert(!fclose(seed));
    int atomic=(int)do_open("/savedata0/state",2|0x400,0644);assert(atomic>=3);assert(do_write(atomic,"next",4)==4);
    char check[16]={0};seed=fopen(state,"rb");assert(seed&&fread(check,1,15,seed)==8&&!memcmp(check,"old-safe",8));fclose(seed);
    assert(!do_close(atomic));seed=fopen(state,"rb");memset(check,0,sizeof(check));assert(seed&&fread(check,1,15,seed)==4&&!memcmp(check,"next",4));fclose(seed);
    pid_t child=fork();assert(child>=0);
    if(!child){int fd=(int)do_open("/savedata0/state",2|0x400,0644);if(fd<3||do_write(fd,"incomplete",10)!=10)_exit(2);_exit(0);}
    int status=0;assert(waitpid(child,&status,0)==child&&WIFEXITED(status)&&WEXITSTATUS(status)==0);
    runtime_file_unmount("/savedata0");assert(!runtime_file_mount("/savedata0",savedir));
    seed=fopen(state,"rb");memset(check,0,sizeof(check));assert(seed&&fread(check,1,15,seed)==4&&!memcmp(check,"next",4));fclose(seed);
    runtime_file_unmount("/savedata0");assert(!unlink(state)&&!rmdir(savedir));
    puts("Atomic saves: original kept while writing and after interrupted process; completed save committed; stale temp cleaned PASS");
    assert(!unlink(link) && !unlink(source) && !rmdir(game));
    const char *dirs[]={"temp0","download0","data"};
    for (int i=0;i<3;++i) { char p[1024]; snprintf(p,sizeof(p),"%s/%s",user,dirs[i]); assert(!rmdir(p)); }
    bb_save_access_release();
    char lease_path[1024]; snprintf(lease_path,sizeof(lease_path),"%s/.crowned-workshop-save.lock",user);
    assert(!unlink(lease_path));
    assert(!rmdir(user) && !rmdir(root));
    puts("Guest mod files: reads, stat, merged listing, readonly assets and writable saves PASS");
}
