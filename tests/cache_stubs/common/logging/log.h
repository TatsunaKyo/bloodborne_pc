// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <atomic>
#include <stdexcept>
namespace CacheTest {
inline std::atomic<unsigned> warnings{};
template <class... T> void Log(const char *, const T &...) { ++warnings; }
} // namespace CacheTest
#define LOG_WARNING(category, ...) CacheTest::Log(__VA_ARGS__)
#define LOG_INFO(category, ...) CacheTest::Log(__VA_ARGS__)
#define LOG_ERROR(category, ...) CacheTest::Log(__VA_ARGS__)
#define ASSERT_MSG(condition, ...)                                             \
  do {                                                                         \
    if (!(condition))                                                          \
      throw std::runtime_error("fresh shader assertion");                      \
  } while (0)
#define UNREACHABLE() throw std::runtime_error("unreachable")
