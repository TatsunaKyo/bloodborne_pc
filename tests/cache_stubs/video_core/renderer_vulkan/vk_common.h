// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "common/types.h"
#include <cstddef>
#include <string>
#include <utility>
namespace vk {
enum class Result { eSuccess, eErrorUnknown };
using ShaderModule = void *;
struct ShaderModuleCreateInfo {
  size_t codeSize;
  const u32 *pCode;
};
inline unsigned calls{};
inline Result next_result = Result::eSuccess;
struct Device {
  std::pair<Result, ShaderModule>
  createShaderModule(const ShaderModuleCreateInfo &) const {
    ++calls;
    return {next_result, reinterpret_cast<void *>(size_t(1))};
  }
};
inline std::string to_string(Result) { return "fixture driver status"; }
} // namespace vk
