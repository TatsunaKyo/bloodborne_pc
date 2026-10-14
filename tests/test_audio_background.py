# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the production audio port code and pause gate with an SDL recording device.

The recorded device verifies playback/queue ownership, not a physical sound card.
Only the wall-clock wait and SDL boundary are supplied by the fixture.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = 'src/runtime_audio.c'
BASE = 'a3df0604a808a4bb9fb52c03e3791ae956ba0e0f'

PRELUDE = r'''
#include <algorithm>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <future>
#include <mutex>
#include <thread>
#include <vector>
#include "bbport_background.h"
#include "bbgpu.h"
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
using pthread_mutex_t=SRWLOCK;
using pthread_cond_t=CONDITION_VARIABLE;
using pthread_once_t=INIT_ONCE;
#define PTHREAD_MUTEX_INITIALIZER SRWLOCK_INIT
#define PTHREAD_COND_INITIALIZER CONDITION_VARIABLE_INIT
#define PTHREAD_ONCE_INIT INIT_ONCE_STATIC_INIT
int pthread_mutex_init(pthread_mutex_t* m,void*){InitializeSRWLock(m);return 0;}
int pthread_mutex_lock(pthread_mutex_t* m){AcquireSRWLockExclusive(m);return 0;}
int pthread_mutex_unlock(pthread_mutex_t* m){ReleaseSRWLockExclusive(m);return 0;}
int pthread_cond_wait(pthread_cond_t* c,pthread_mutex_t* m){return !SleepConditionVariableSRW(c,m,INFINITE,0);}
int pthread_cond_broadcast(pthread_cond_t* c){WakeAllConditionVariable(c);return 0;}
struct OnceArg {void(*function)();};
BOOL CALLBACK OnceThunk(PINIT_ONCE,PVOID p,PVOID*){static_cast<OnceArg*>(p)->function();return TRUE;}
int pthread_once(pthread_once_t* once,void(*fn)()){OnceArg p{fn};return !InitOnceExecuteOnce(once,OnceThunk,&p,nullptr);}
#else
#include <pthread.h>
#endif
#define ABI
#define _Static_assert static_assert
using namespace std::chrono_literals;
using Clock=std::chrono::steady_clock;
static uint64_t now_ns(){return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count());}
static void sleep_until(uint64_t ns){std::this_thread::sleep_until(Clock::time_point(std::chrono::nanoseconds(ns)));}
constexpr int SDL_INIT_AUDIO=1,SDL_AUDIO_F32=2,SDL_AUDIO_S16=3,SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK=1;
struct SDL_AudioSpec{int format,channels,freq;};
struct SDL_AudioStream {std::mutex mutex;bool paused=true,closed=false;std::vector<unsigned char> queued;};
static bool open_fail;
bool SDL_InitSubSystem(int){return true;}
const char* SDL_GetCurrentAudioDriver(){return "recording";}
const char* SDL_GetError(){return "fixture open failure";}
SDL_AudioStream* SDL_OpenAudioDeviceStream(int,const SDL_AudioSpec*,void*,void*){
    return open_fail ? nullptr : new SDL_AudioStream;
}
bool SDL_PauseAudioStreamDevice(SDL_AudioStream* s){std::scoped_lock lock{s->mutex};s->paused=true;return !s->closed;}
bool SDL_ResumeAudioStreamDevice(SDL_AudioStream* s){std::scoped_lock lock{s->mutex};s->paused=false;return !s->closed;}
void SDL_DestroyAudioStream(SDL_AudioStream* s){std::scoped_lock lock{s->mutex};s->closed=true;}
int SDL_GetAudioStreamQueued(SDL_AudioStream* s){std::scoped_lock lock{s->mutex};return int(s->queued.size());}
bool SDL_PutAudioStreamData(SDL_AudioStream* s,const void* p,int n){
    std::scoped_lock lock{s->mutex};assert(!s->closed);auto b=static_cast<const unsigned char*>(p);
    s->queued.insert(s->queued.end(),b,b+n);return true;
}
static bool IsPaused(SDL_AudioStream* s){if(!s)return true;std::scoped_lock lock{s->mutex};return s->paused;}
static std::vector<unsigned char> Queued(SDL_AudioStream* s){if(!s)return {};std::scoped_lock lock{s->mutex};return s->queued;}
static size_t Consume(SDL_AudioStream* s,size_t n){
    if(!s)return 0;std::scoped_lock lock{s->mutex};if(s->paused)return 0;
    n=std::min(n,s->queued.size());s->queued.erase(s->queued.begin(),s->queued.begin()+n);return n;
}
'''

MAIN = r'''
int main(int argc,char**argv){
    const bool silent=argc>1 && std::strcmp(argv[1],"silent")==0;
    const bool failure=argc>1 && std::strcmp(argv[1],"open-failure")==0;
    open_fail=failure;
    if(silent){
#ifdef _WIN32
        _putenv_s("BB_AUDIO","none");
#else
        setenv("BB_AUDIO","none",1);
#endif
    }
    std::vector<int16_t> pcm(512,1234);
#if CONTROL
    assert(audio_init()==0);
    int a=audio_open(0,0,0,256,48000,1);assert(a>=0);
    BbBackground::Update(true);
    assert(!IsPaused(ports[a&0xff].stream));
    assert(audio_output(a,pcm.data())==512);
    std::puts("CONTROL: R35 leaves the SDL device playing and accepts audio buffers during background Pause.");
    BbBackground::Update(false);audio_close(a);return 7;
#else
    // Launch out of focus before the audio library initializes.
    BbBackground::Update(true);assert(audio_init()==0);
    int a=audio_open(0,0,0,256,48000,1),b=audio_open(0,1,0,256,48000,1);
    assert(a>=0 && b>=0 && IsPaused(ports[a&0xff].stream) && IsPaused(ports[b&0xff].stream));
    auto first=std::async(std::launch::async,[&]{return audio_output(a,pcm.data());});
    assert(first.wait_for(30ms)==std::future_status::timeout);
    BbBackground::Update(false);assert(first.wait_for(300ms)==std::future_status::ready && first.get()==512);
    assert(audio_init()==ERR_ALREADY_INIT);
    OutputParam out[]={{a,pcm.data()},{b,pcm.data()}};
    assert(audio_outputs(out,2)==512);
    for(int cycle=0;cycle<12;++cycle){
        BbBackground::Update(true);
        auto* sa=ports[a&0xff].stream;auto* sb=ports[b&0xff].stream;
        assert(IsPaused(sa) && IsPaused(sb));
        const auto before_a=Queued(sa),before_b=Queued(sb);
        assert(Consume(sa,4096)==0 && Consume(sb,4096)==0);
        // A stale wall-clock deadline or queue controller must not survive resume.
        for(int handle:{a,b}){
            auto& p=ports[handle&0xff];pthread_mutex_lock(&p.lock);
            p.next_deadline_ns=now_ns()+2'000'000'000ull;p.window_count=31;p.adjust_ns=777;
            pthread_mutex_unlock(&p.lock);
        }
        auto pending=std::async(std::launch::async,[&]{return audio_outputs(out,2);});
        assert(pending.wait_for(20ms)==std::future_status::timeout);
        assert(Queued(sa)==before_a && Queued(sb)==before_b);
        assert(audio_output(-1,nullptr)==ERR_INVALID_PORT);
        BbBackground::Update(false);
        assert(pending.wait_for(300ms)==std::future_status::ready && pending.get()==512);
        for(auto pair:{std::pair{sa,&before_a},std::pair{sb,&before_b}}){
            const auto after=Queued(pair.first);
            assert(after.size()>=pair.second->size());
            assert(std::equal(pair.second->begin(),pair.second->end(),after.begin()));
            if(pair.first)assert(!IsPaused(pair.first));
        }
        assert(ports[a&0xff].window_count<=1 && ports[b&0xff].window_count<=1);
        if(sa) assert(Consume(sa,1024)==1024);
        if(sb) assert(Consume(sb,1024)==1024);
    }
    // A port opened while paused starts paused; a parked output rechecks close.
    BbBackground::Update(true);
    int voice=audio_open(0,2,0,256,48000,1);assert(voice>=0 && IsPaused(ports[voice&0xff].stream));
    auto closed=std::async(std::launch::async,[&]{return audio_output(voice,pcm.data());});
    assert(closed.wait_for(20ms)==std::future_status::timeout);
    assert(audio_close(voice)==0);
    BbBackground::Update(false);
    assert(closed.wait_for(300ms)==std::future_status::ready && closed.get()==ERR_NOT_OPENED);
    // Ordinary foreground audio and conversion remain usable after the cycles.
    int32_t volume[8]={16384,32768,32768,32768,32768,32768,32768,32768};
    assert(audio_volume(a,1,volume)==0 && audio_output(a,pcm.data())==512);
    auto data=Queued(ports[a&0xff].stream);
    if(!data.empty()){
        int16_t left,right;std::memcpy(&left,data.data()+data.size()-1024,2);
        std::memcpy(&right,data.data()+data.size()-1022,2);assert(left==617 && right==1234);
    }
    assert(audio_close(a)==0 && audio_close(b)==0);
    bbgpu_set_background_audio_callback(nullptr);
    std::printf("PASS: production audio startup pause, 12 pause/resume cycles, two-port feeding, retained PCM, fresh cadence, close while parked and volume conversion (%s).\n",silent?"silent sink":failure?"failed device":"SDL recording device");
    return 0;
#endif
}
'''


def body(source):
    text = source[source.index('#define PORTS'):source.index('static const RuntimeExport exports')]
    a, b = text.index('static uint64_t now_ns'), text.index('static int sdl_audio')
    # C implicitly zero-initializes this static array; C++ requires the spelling.
    return (text[:a] + text[b:]).replace('static const unsigned char silence[2048*8*4];',
                                        'static const unsigned char silence[2048*8*4]={};')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='workshop-audio-') as tmp:
        folder = args.prepare.resolve() if args.prepare else Path(tmp)
        folder.mkdir(parents=True, exist_ok=True)
        old = subprocess.check_output(['git', 'show', BASE + ':' + SOURCE], cwd=ROOT, text=True)
        for name, source, control in [('revision35', old, True), ('current', (ROOT / SOURCE).read_text(), False)]:
            cpp = folder / (name + '.cpp')
            cpp.write_text('#define CONTROL ' + str(int(control)) + '\n' + PRELUDE + body(source) + MAIN)
            if args.prepare:
                continue
            binary = folder / name
            subprocess.run(['g++', '-std=c++20', '-O1', '-pthread', '-UNDEBUG', '-I', str(ROOT / 'gpu'),
                            '-I', str(ROOT / 'gpu/shim'), str(cpp), str(ROOT / 'gpu/shim/bbport_background.cpp'),
                            '-o', str(binary)], check=True)
            for mode in (['recording'] if control else ['recording', 'silent', 'open-failure']):
                result = subprocess.run([str(binary), mode], timeout=15)
                if result.returncode != (7 if control else 0):
                    raise RuntimeError(f'{name}/{mode}: unexpected exit {result.returncode}')


if __name__ == '__main__':
    main()
