// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include "video_core/buffer_cache/region_definitions.h"

namespace VideoCore::ColdWriteWatch {

inline constexpr size_t Pages = 16; // 64 KiB of host pages, within one 4 MiB tracker region

// Adjacent cold pages may be protected before their first upload, but they must
// remain CPU-dirty. Never include a hole, a GPU-written page or a known writer.
template <class Mapped>
RegionBits Expand(VAddr base, const RegionBits& newly_protected, const RegionBits& eligible,
                  Mapped&& mapped, size_t pages = Pages) {
    RegionBits result;
    if (eligible.None() || !pages || pages > Pages || (pages & (pages - 1))) return result;
    size_t visited_end = 0;
    for (const auto& [begin, end] : newly_protected) {
        for (size_t page = std::max(begin & ~(pages - 1), visited_end); page < end;
             page += pages) {
            visited_end = page + pages;
            if (eligible.AnyInRange(page, visited_end) &&
                mapped(base + page * TRACKER_BYTES_PER_PAGE, pages * TRACKER_BYTES_PER_PAGE)) {
                result.SetRange(page, visited_end);
            }
        }
    }
    return result & eligible;
}

} // namespace VideoCore::ColdWriteWatch
