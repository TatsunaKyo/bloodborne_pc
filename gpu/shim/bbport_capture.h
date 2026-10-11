// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdio>
#include <cstdlib>

namespace BbCapture {

class GeometryKey {
public:
    bool Press(bool f8, bool repeat) {
        const char* enabled = std::getenv("BB_GEOMETRY_CAPTURE");
        if (!f8 || repeat || !enabled || enabled[0] != '1') return false;
        const char* trigger = std::getenv("BB_DUMP_TRIGGER");
        if (!trigger) return false;
        if (!requested) {
            if (FILE* file = std::fopen(trigger, "wb")) {
                std::fclose(file);
                requested = true;
                if (const char* passes = std::getenv("BB_CAPTURE_TRIGGER")) {
                    if (FILE* frame = std::fopen(passes, "wb")) std::fclose(frame);
                }
                std::puts("Geometry capture: F8 requested scene-input/output frames");
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
