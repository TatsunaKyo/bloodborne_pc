// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <algorithm>
#include <cassert>
#include <map>
#include <vector>
#include "bbport_hitch.h"
#include "common/types.h"
#include "video_core/renderer_vulkan/vk_common.h"

namespace VideoCore {

// Sparse bindings retain their physical storage for the arena's lifetime. Allocate
// small bindings from shared slabs instead of entering the driver for every new
// mesh. This only suballocates physical memory: it never maps extra guest pages,
// reuses a live slice, or changes the sparse-bind/submit semaphore ordering.
class SparseMemoryPool {
public:
    struct Slice {
        vk::DeviceMemory memory{};
        u64 offset{}; // bytes, always a multiple of the sparse block alignment
    };

    SparseMemoryPool() = default;
    SparseMemoryPool(const SparseMemoryPool&) = delete;
    SparseMemoryPool& operator=(const SparseMemoryPool&) = delete;

    ~SparseMemoryPool() {
        for (auto memory : allocations) device.freeMemory(memory);
    }

    void Initialize(vk::Device device_, u32 type_, u64 alignment_, u64 max_allocation,
                    u64 heap_bytes, std::vector<u32> alternatives = {}) {
        assert(allocations.empty());
        device = device_;
        type = type_;
        fallback_types=std::move(alternatives);
        alignment = alignment_;
        // At most 16 MiB per new slab, smaller on small heaps. Large requests
        // keep exact-size allocations, preventing slabs with large unused tails.
        const u64 target = std::min({u64{16} << 20, heap_bytes / 256, max_allocation});
        slab_bytes = std::max(alignment, target - target % alignment);
    }

    vk::ResultValue<Slice> Allocate(u64 bytes) {
        assert(bytes && alignment && bytes % alignment == 0);
        if (auto it = tails.lower_bound(bytes); it != tails.end()) {
            auto slice = it->second;
            const u64 remaining = it->first - bytes;
            auto tail = tails.extract(it);
            if (remaining) {
                tail.key() = remaining;
                tail.mapped().offset += bytes;
                tails.insert(std::move(tail));
            }
            return {vk::Result::eSuccess, slice};
        }
        u64 allocated = bytes < slab_bytes / 4 ? slab_bytes : bytes;
        const auto allocate_type = [&](u64 size,u32 memory_type) {
            const vk::MemoryAllocateFlagsInfo flags{.flags=vk::MemoryAllocateFlagBits::eDeviceAddress};
            const vk::MemoryAllocateInfo info{.pNext=&flags,.allocationSize = size, .memoryTypeIndex = memory_type};
            BbHitch::Scope hitch{"vkAllocateMemory sparse backing"};
            return device.allocateMemory(info);
        };
        const auto allocate=[&](u64 size) {return allocate_type(size,type);};
        auto result = allocate(allocated);
        if (result.result != vk::Result::eSuccess && allocated > bytes &&
            (result.result == vk::Result::eErrorOutOfDeviceMemory ||
             result.result == vk::Result::eErrorOutOfHostMemory)) {
            // Pool growth is optional when memory is tight; preserve the former
            // exact-size allocation behavior rather than rejecting a valid bind.
            allocated = bytes;
            result = allocate(bytes);
        }
        if (result.result == vk::Result::eErrorOutOfDeviceMemory) {
            for (u32 alternative:fallback_types) {
                allocated=bytes;
                result=allocate_type(bytes,alternative);
                if (result.result!=vk::Result::eErrorOutOfDeviceMemory) break;
            }
        }
        if (result.result != vk::Result::eSuccess) return {result.result, {}};
        allocations.push_back(result.value);
        if (allocated > bytes) tails.emplace(allocated - bytes, Slice{result.value, bytes});
        return {vk::Result::eSuccess, {result.value, 0}};
    }

private:
    vk::Device device{};
    u32 type{};
    std::vector<u32> fallback_types;
    u64 alignment{}, slab_bytes{};
    std::vector<vk::DeviceMemory> allocations;
    std::multimap<u64, Slice> tails; // best fit; retain and reuse older slab tails
};

} // namespace VideoCore
