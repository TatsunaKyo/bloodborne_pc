// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <span>
#include <vector>

namespace Shader::MotionAddress {

// Portable SPIR-V uses these relocations instead of a previous process's BDA.
// Link a private copy immediately before creating the Vulkan shader module;
// the on-disk binary and captured compiler output remain process independent.
inline constexpr uint64_t Params = 0x4242504D00000001ull;
inline constexpr uint64_t ParamsTail = Params + 16;
inline constexpr uint64_t Positions = 0x4242504F00000001ull;
inline uint64_t params_address{}, positions_address{};

enum class Result { Unchanged, Linked, Invalid };

inline Result Link(std::span<const uint32_t> code, std::vector<uint32_t>& output) {
    output.clear();
    if (code.size() < 5) return Result::Unchanged;
    uint32_t uint64_type{};
    unsigned counts[3]{};
    for (size_t at = 5; at < code.size();) {
        const uint32_t count = code[at] >> 16, opcode = code[at] & 0xffff;
        if (!count || count > code.size() - at) return Result::Invalid;
        // OpTypeInt: result id, width, signedness.
        if (opcode == 21 && count == 4 && code[at + 2] == 64 && !code[at + 3])
            uint64_type = code[at + 1];
        // OpConstant: only unsigned 64-bit scalar constants can be relocations.
        if (opcode == 43 && count == 5 && uint64_type && code[at + 1] == uint64_type) {
            const uint64_t value = uint64_t(code[at + 3]) | (uint64_t(code[at + 4]) << 32);
            const int index = value == Params ? 0 : value == ParamsTail ? 1 : value == Positions ? 2 : -1;
            if (index >= 0) {
                if (++counts[index] != 1) return Result::Invalid;
                if (output.empty()) output.assign(code.begin(), code.end());
                const uint64_t address = index == 2 ? positions_address : params_address + (index == 1 ? 16 : 0);
                output[at + 3] = uint32_t(address);
                output[at + 4] = uint32_t(address >> 32);
            }
        }
        at += count;
    }
    if (!counts[0] && !counts[1] && !counts[2]) return Result::Unchanged;
    if (counts[0] != 1 || counts[1] != 1 || counts[2] != 1 || !params_address ||
        !positions_address || params_address > std::numeric_limits<uint64_t>::max() - 16)
        return Result::Invalid;
    return Result::Linked;
}

} // namespace Shader::MotionAddress
