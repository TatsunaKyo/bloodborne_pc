// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
#pragma once
#include <algorithm>
#include <cstdint>

namespace VideoCore::VertexFetch {
struct Range { uint32_t offset{}, size{}; };

// A descriptor defines binding bounds, not the amount a direct draw fetches.
// Keep the original binding/vertex ID; only the host upload footprint changes.
inline Range Bytes(uint32_t descriptor_bytes, uint32_t stride, uint32_t first,
                   uint32_t count, uint64_t attribute_end) {
    const Range full{0, descriptor_bytes};
    if (!stride || !count || !attribute_end) return full;
    const uint64_t begin = uint64_t(first) * stride;
    const uint64_t end = (uint64_t(first) + count - 1) * stride + attribute_end;
    if (begin >= descriptor_bytes || end <= begin) return full;
    return {uint32_t(begin), uint32_t(std::min<uint64_t>(descriptor_bytes, end) - begin)};
}
} // namespace VideoCore::VertexFetch
