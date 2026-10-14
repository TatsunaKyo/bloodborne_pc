// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdio>
#include <cstdlib>

namespace BbCapture {

class GeometryKey {
public:
    bool Press(bool f8, bool repeat) {
        const char* fg_trigger = std::getenv("BB_FG_CAPTURE_TRIGGER");
        const char* enabled = std::getenv("BB_GEOMETRY_CAPTURE");
        if (!f8 || repeat || ((!fg_trigger || !*fg_trigger) &&
            (!enabled || enabled[0] != '1'))) return false;
        const char* trigger = fg_trigger && *fg_trigger ? fg_trigger : std::getenv("BB_DUMP_TRIGGER");
        if (!trigger) return false;
        if (!requested) {
            if (FILE* file = std::fopen(trigger, "wb")) {
                std::fclose(file);
                requested = true;
                if (const char* passes = fg_trigger ? nullptr : std::getenv("BB_CAPTURE_TRIGGER")) {
                    if (FILE* frame = std::fopen(passes, "wb")) std::fclose(frame);
                }
                std::puts(fg_trigger ? "NVIDIA FG capture: F8 requested the tagged inputs and real backbuffer"
                                    : "Geometry capture: F8 requested scene-input/output frames");
                std::fflush(stdout);
            } else {
                std::puts("Geometry capture: cannot create the capture trigger");
            }
        }
        return true;
    }

private:
    bool requested = false;
};

} // namespace BbCapture
