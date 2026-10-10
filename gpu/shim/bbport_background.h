// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <cstdint>
#include <stop_token>

namespace BbBackground {
// The SDL thread stays runnable. Game submissions and presentation wait without
// holding a renderer lock, so activation never depends on a suspended HWND.
void Update(bool pause);
bool Paused();
void Wait(std::stop_token stop = {});
std::uint64_t PausedNanoseconds();
}
