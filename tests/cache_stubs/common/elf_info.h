// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "common/logging/log.h"
namespace Common {
struct ElfInfo {
  static ElfInfo &Instance() {
    static ElfInfo info;
    return info;
  }
  const char *GameSerial() const { return "CUSA_CACHE_TEST"; }
};
} // namespace Common
