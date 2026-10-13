// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include "common/types.h"
#include <algorithm>
#include <array>
#include <cstring>
#include <span>
#include <stdexcept>
#include <vector>

namespace Storage::Blob {
inline constexpr std::array<u8, 8> Magic{'C', 'W', 'C', 'A',
                                         'C', 'H', 'E', '1'};
inline constexpr size_t HeaderSize = 32;

constexpr size_t PayloadLimit(u32 kind) {
  constexpr std::array<size_t, 4> limits{4 * 1024 * 1024, 32 * 1024 * 1024,
                                         4 * 1024 * 1024, 64 * 1024};
  return kind < limits.size() ? limits[kind] : 0;
}

inline constexpr auto CrcTable = [] {
  std::array<u32, 256> table{};
  for (u32 i = 0; i < table.size(); ++i) {
    u32 value = i;
    for (int bit = 0; bit < 8; ++bit)
      value = (value >> 1) ^ ((value & 1) ? 0xedb88320u : 0u);
    table[i] = value;
  }
  return table;
}();

inline u32 Checksum(std::span<const u8> data) {
  u32 value = ~u32{0};
  for (u8 byte : data)
    value = CrcTable[(value ^ byte) & 255] ^ (value >> 8);
  return ~value;
}

inline u64 ReadLe(std::span<const u8> data, size_t offset, size_t count) {
  u64 value = 0;
  for (size_t i = 0; i < count; ++i)
    value |= u64{data[offset + i]} << (i * 8);
  return value;
}

inline void WriteLe(std::span<u8> data, size_t offset, u64 value,
                    size_t count) {
  for (size_t i = 0; i < count; ++i)
    data[offset + i] = u8(value >> (i * 8));
}

inline std::vector<u8> Encode(u32 kind, std::span<const u8> payload) {
  if (!PayloadLimit(kind) || payload.size() > PayloadLimit(kind))
    throw std::runtime_error("Shader cache payload exceeds its limit");
  std::vector<u8> result(HeaderSize + payload.size());
  std::ranges::copy(Magic, result.begin());
  WriteLe(result, 8, 1, 4);
  WriteLe(result, 12, kind, 4);
  WriteLe(result, 16, payload.size(), 8);
  WriteLe(result, 24, Checksum(payload), 4);
  std::ranges::copy(payload, result.begin() + HeaderSize);
  return result;
}

// The payload format remains unchanged. Old unwrapped records can still be
// read.
inline bool Decode(u32 kind, std::span<const u8> data,
                   std::span<const u8> &payload) {
  payload = {};
  const size_t limit = PayloadLimit(kind);
  if (!limit || data.empty() || data.size() > limit + HeaderSize)
    return false;
  const bool wrapped = data.size() >= Magic.size() &&
                       std::ranges::equal(data.first(Magic.size()), Magic);
  if (!wrapped) {
    if (data.size() < Magic.size() &&
        std::ranges::equal(data, std::span(Magic).first(data.size())))
      return false;
    if (data.size() > limit)
      return false;
    payload = data;
    return true;
  }
  if (data.size() < HeaderSize || ReadLe(data, 8, 4) != 1 ||
      ReadLe(data, 12, 4) != kind || ReadLe(data, 28, 4) != 0 ||
      ReadLe(data, 16, 8) != data.size() - HeaderSize)
    return false;
  payload = data.subspan(HeaderSize);
  if (payload.size() > limit || ReadLe(data, 24, 4) != Checksum(payload)) {
    payload = {};
    return false;
  }
  return true;
}

inline bool WellFormedSpirv(std::span<const u32> code) {
  if (code.size() < 5 || code[0] != 0x07230203 || code[1] < 0x00010000 ||
      code[1] > 0x00010600 || (code[1] & 0xff) || !code[3] ||
      code[3] > 0x3fffff || code[4])
    return false;
  bool memory_model = false, entry_point = false;
  for (size_t pos = 5; pos < code.size();) {
    const size_t count = code[pos] >> 16;
    const u32 opcode = code[pos] & 0xffff;
    if (!count || count > code.size() - pos)
      return false;
    if (opcode == 14) {
      if (count != 3)
        return false;
      memory_model = true;
    }
    if (opcode == 15) {
      if (count < 4)
        return false;
      entry_point = true;
    }
    pos += count;
  }
  return memory_model && entry_point;
}
} // namespace Storage::Blob
