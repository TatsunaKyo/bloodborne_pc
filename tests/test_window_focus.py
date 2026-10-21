# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Execute the production window event pump with controlled SDL/Win32 focus snapshots."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


def prepare(directory):
    directory.mkdir(parents=True, exist_ok=True)
    source = (ROOT / 'gpu/shim/window.cpp').read_text()
    previous = subprocess.check_output(['git', 'show',
        'b397bc30648ae215a7c381476300fd5c69be846f:gpu/shim/window.cpp'], cwd=ROOT, text=True)
    wanted = function((ROOT / 'gpu/shim/bbport_nvidia.cpp').read_text(), 'bool Wanted()')
    fixture = r'''
#include <atomic>
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <deque>
#include <mutex>
#include <string>
#include "sdl_window.h"
#include "bbport_settings.h"
#include "bbport_background.h"
#include "bbport_capture.h"
struct SDL_Window {};
using HWND = void*;
enum { SDL_WINDOW_INPUT_FOCUS=1, SDL_WINDOW_MINIMIZED=2,
    SDL_EVENT_KEY_DOWN=10, SDL_EVENT_TEXT_INPUT, SDL_EVENT_GAMEPAD_BUTTON_DOWN,
    SDL_EVENT_QUIT, SDL_EVENT_WINDOW_FOCUS_LOST=20, SDL_EVENT_WINDOW_FOCUS_GAINED,
    SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED, SDL_EVENT_WINDOW_RESIZED,
    SDL_EVENT_WINDOW_CLOSE_REQUESTED, SDL_EVENT_WINDOW_FIRST=20, SDL_EVENT_WINDOW_LAST=30,
    SDL_SCANCODE_F8=1, SDLK_BACKSPACE=8, SDLK_RETURN=13, SDLK_KP_ENTER=14, SDLK_ESCAPE=27,
    SDL_GAMEPAD_BUTTON_SOUTH=0, SDL_GAMEPAD_BUTTON_EAST=1 };
enum {SDL_EVENT_MOUSE_BUTTON_DOWN=100,SDL_EVENT_MOUSE_BUTTON_UP,SDL_EVENT_MOUSE_WHEEL,
      SDL_EVENT_MOUSE_MOTION,SDL_EVENT_GAMEPAD_ADDED,SDL_EVENT_GAMEPAD_AXIS_MOTION};
struct SDL_Event {
    int type{};
    struct { unsigned windowID=1; } window;
    struct { int scancode{}, key{}; bool repeat{}; } key;
    struct { std::string text; } text;
    struct { int button{},which{}; } gbutton,button;
    struct { int which{}; } gdevice;
    struct { int which{},value{}; } gaxis;
    struct {float xrel{},yrel{};} motion;
    struct {float x{},y{};} wheel;
};
unsigned SDL_BUTTON_MASK(unsigned button){return 1u<<button;}
uint64_t SDL_GetTicks(){return 0;}
const char* SDL_GetGamepadNameForID(int){return "fixture";}
int SDL_GetGamepadTypeForID(int){return 0;}
const char* SDL_GetGamepadStringForType(int){return "fixture";}
namespace BbPrompts {enum Device {Keyboard,PlayStation};void OnInput(Device){}void OnControllerConnected(Device){}void Apply(){}}
namespace Core {struct BloodborneCam {static BloodborneCam& Instance(){static BloodborneCam c;return c;}bool IsEnabled()const{return false;}bool IsLockedOn()const{return false;}};}
SDL_Window target;
int game_handle, other_handle;
HWND foreground=&other_handle;
bool visible=true, minimized=false, native=true, consume_focus=false;
unsigned flags=0;
std::deque<SDL_Event> events;
unsigned SDL_GetWindowFlags(SDL_Window*) { return flags; }
unsigned SDL_GetWindowID(SDL_Window*) { return 1; }
HWND GetForegroundWindow() { return foreground; }
bool IsWindowVisible(HWND) { return visible; }
bool IsIconic(HWND) { return minimized; }
bool SDL_PollEvent(SDL_Event* out) {
    if(events.empty()) return false;
    *out=events.front(); events.pop_front(); return true;
}
void SDL_StartTextInput(SDL_Window*) {}
void SDL_StopTextInput(SDL_Window*) {}
void SDL_GetWindowSizeInPixels(SDL_Window*, int* w, int* h) { *w=1920; *h=1080; }
namespace BbOverlay {
int saves=0, focus_events=0;
bool HandleEvent(const SDL_Event& e) {
    if(e.type==SDL_EVENT_WINDOW_FOCUS_GAINED || e.type==SDL_EVENT_WINDOW_FOCUS_LOST) {
        ++focus_events; return consume_focus;
    }
    return false;
}
void SavePendingSettings() { ++saves; }
void UpdateTextInput(SDL_Window*) {}
}
namespace BbNvidia {
int shutdowns=0;
void BeforeSwapchainChange() { ++shutdowns; }
@WANTED@
}
namespace Frontend {
constexpr uint64_t kWheelPulseMs=50;
std::array<std::atomic<uint64_t>,4> g_wheel_expiry_ms{};
BbPrompts::Device PadDevice(int){return BbPrompts::PlayStation;}
WindowSDL::WindowSDL(s32 w,s32 h,const char*) : width{w},height{h} {
    window=&target;
    window_info.type=native ? WindowSystemType::Windows : WindowSystemType::X11;
    window_info.render_surface=&game_handle;
    @INITIAL@
}
WindowSDL::~WindowSDL() {}
void WindowSDL::ApplyWindowMode() {}
void WindowSDL::UpdateTextTitle() {}
void WindowSDL::UpdateMouseCapture() {}
void WindowSDL::UpdateMouseCamera() {}
#ifndef _WIN32
#define _WIN32
#endif
@REFRESH@
@POLL@
}
void check(bool ok,const char* label) {
    if(!ok) { std::fprintf(stderr,"FAIL: %s\n",label); std::exit(7); }
}
void event(int type,unsigned id=1) { SDL_Event e; e.type=type; e.window.windowID=id; events.push_back(e); }
int main() {
    using namespace BbSettings;
    auto& s=Get();
    s.variable_frame_time=true;s.real_fps_limit=65;s.generated_fps_limit=130;
    s.limit_generated_fps=true;s.frame_generation=FrameGenerationNvidia;
    s.frame_generation_cap_multiplier=2;s.reflex=1;
    int cases=0;
    for(int mode : {Background30,Background60,BackgroundPause}) {
        s.background_mode=mode;s.window_focused=true;
        foreground=&other_handle;flags=0;visible=true;minimized=false;
        consume_focus=false;
        Frontend::WindowSDL window(1920,1080,"test");
        window.PollEvents();
        check(!s.window_focused,"startup respects actual foreground HWND, not stale SDL flags");
        check(EffectiveFrameLimit(120)==unsigned(mode==Background60 ? 60 : 30),"startup background cap");
        check(!BbNvidia::Wanted(),"FG and Reflex sleep while in background");
        check(BbBackground::Paused()==(mode==BackgroundPause),"startup pause policy");
        ++cases;

        // No activation event at all: one live event-pump iteration must resume.
        foreground=&game_handle;flags=0;
        window.PollEvents();
        check(s.window_focused && EffectiveFrameLimit(120)==65,"single foreground poll restores 65 real / 130 total cap");
        check(BbNvidia::Wanted() && !BbBackground::Paused(),"foreground re-enables FG/Reflex and wakes paused workers");
        ++cases;

        // A stale loss may arrive after acquisition; event order is not authority.
        event(SDL_EVENT_WINDOW_FOCUS_GAINED);event(SDL_EVENT_WINDOW_FOCUS_LOST);
        window.PollEvents();
        check(s.window_focused && EffectiveFrameLimit(120)==65,"queued stale focus loss cannot strand foreground cap");
        ++cases;

        foreground=&other_handle;consume_focus=true;
        event(SDL_EVENT_WINDOW_FOCUS_GAINED);
        window.PollEvents();
        check(!s.window_focused && !BbNvidia::Wanted(),"consumed or stale focus gain cannot bypass background policy");
        ++cases;

        foreground=&game_handle;window.PollEvents();
        check(s.window_focused && !BbBackground::Paused(),"missing gain still resumes when overlay consumes events");
        ++cases;

        minimized=true;window.PollEvents();
        check(!s.window_focused,"minimized foreground handle is background");
        minimized=false;window.PollEvents();
        check(s.window_focused && EffectiveFrameLimit(120)==65,"restore without event restores cap");
        ++cases;

        visible=false;window.PollEvents();check(!s.window_focused,"hidden window is background");
        visible=true;window.PollEvents();check(s.window_focused,"visible foreground window resumes");
        ++cases;

        event(SDL_EVENT_WINDOW_CLOSE_REQUESTED,2);
        check(window.PollEvents(),"another SDL window cannot close the game or change its policy");
        ++cases;
    }
    native=false;s.background_mode=Background30;s.window_focused=true;
    flags=0;Frontend::WindowSDL fallback(1920,1080,"fallback");fallback.PollEvents();
    check(!s.window_focused,"SDL focus fallback initially unfocused");
    flags=SDL_WINDOW_INPUT_FOCUS;fallback.PollEvents();
    check(s.window_focused && EffectiveFrameLimit(120)==65,"SDL fallback reconciles missing activation event");
    flags|=SDL_WINDOW_MINIMIZED;fallback.PollEvents();check(!s.window_focused,"SDL minimized fallback");
    flags=SDL_WINDOW_INPUT_FOCUS;fallback.PollEvents();check(s.window_focused,"SDL restored fallback");
    ++cases;
    std::printf("PASS: %d production window-pump scenarios; background startup, missing/stale/consumed events, 65 real / 130 total restoration, FG/Reflex policy, pause wake, native/SDL snapshots.\n",cases);
}
'''.replace('@WANTED@', wanted)
    for name, text in [('revision28',previous),('current',source)]:
        refresh = function(text,'void WindowSDL::RefreshFocusState()') if name=='current' else ''
        initial = 'RefreshFocusState();' if name=='current' else 'BbSettings::Get().window_focused=(SDL_GetWindowFlags(window)&SDL_WINDOW_INPUT_FOCUS)!=0;'
        output = fixture.replace('@INITIAL@',initial).replace('@REFRESH@',refresh)
        output = output.replace('@POLL@',function(text,'bool WindowSDL::PollEvents()'))
        (directory/(name+'.cpp')).write_text(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare',type=Path)
    args=parser.parse_args()
    if args.prepare:
        prepare(args.prepare);return
    with tempfile.TemporaryDirectory(prefix='workshop-window-focus-') as temporary:
        directory=Path(temporary);prepare(directory)
        for name in ('revision28','current'):
            binary=directory/name
            subprocess.run(['g++','-std=c++23','-O1','-pthread','-UNDEBUG',
                '-Igpu/shim','-Igpu/shadps4',str(directory/(name+'.cpp')),
                'gpu/shim/bbport_settings.cpp','gpu/shim/bbport_background.cpp','-o',str(binary)],cwd=ROOT,check=True)
            result=subprocess.run([str(binary)],cwd=ROOT,timeout=30)
            if name=='revision28':
                if result.returncode!=7:raise RuntimeError('Revision 28 must reproduce the focus regression')
                print('PASS: unchanged Revision 28 reproduces the failing startup/focus scenario.',flush=True)
            else:result.check_returncode()


if __name__=='__main__':main()
