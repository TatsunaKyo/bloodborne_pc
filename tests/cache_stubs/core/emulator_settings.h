// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
struct TestEmulatorSettings {
  constexpr bool IsPipelineCacheArchived() const { return false; }
  constexpr bool IsPipelineCacheEnabled() const { return true; }
};
inline constexpr TestEmulatorSettings EmulatorSettings{};
