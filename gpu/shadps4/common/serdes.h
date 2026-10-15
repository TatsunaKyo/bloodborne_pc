// SPDX-FileCopyrightText: Copyright 2025-2026 shadPS4 Emulator Project
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later

#pragma once

#include "common/types.h"

#include <concepts>
#include <cstddef>
#include <cstring>
#include <stdexcept>
#include <string>
#include <type_traits>
#include <utility>
#include <vector>

namespace Serialization {

struct ReadError : std::runtime_error {
  using std::runtime_error::runtime_error;
};

template <typename T>
concept Container = requires(T t) {
  typename T::iterator;
  { t.begin() } -> std::same_as<typename T::iterator>;
  { t.end() } -> std::same_as<typename T::iterator>;
  { t.size() } -> std::convertible_to<std::size_t>;
};

struct Archive {
  void Alloc(size_t size) { container.resize(size); }

  void Grow(size_t size) { container.resize(container.size() + size); }

  void Merge(const Archive &ar) {
    container.insert(container.end(), ar.container.cbegin(),
                     ar.container.cend());
    offset = container.size();
  }

  [[nodiscard]] size_t SizeBytes() const { return container.size(); }

  u8 *CurrPtr() {
    return container.empty() ? nullptr : container.data() + offset;
  }

  [[nodiscard]] size_t RemainingBytes() const {
    return container.size() - offset;
  }

  void Require(size_t size) const {
    if (size > RemainingBytes()) {
      throw ReadError("Truncated shader cache record");
    }
  }

  void Advance(size_t size) {
    Require(size);
    offset += size;
  }

  std::vector<u8> &&TakeOff() {
    offset = 0;
    return std::move(container);
  }

  [[nodiscard]] bool IsEoS() const { return offset >= container.size(); }

  Archive() = default;
  explicit Archive(std::vector<u8> &&v) : container{std::move(v)} {}

private:
  size_t offset{};
  std::vector<u8> container{};

  friend struct Writer;
  friend struct Reader;
};

struct Writer {
  template <typename T> void Write(const T *ptr, size_t size) {
    if (!size) {
      return;
    }
    // Fetch-shader records reserve their fixed fields up front. Grow only by
    // the missing bytes: growing a whole write left an unused tail, which the
    // metadata reader correctly rejected as an incomplete round trip.
    if (size > ar.RemainingBytes()) {
      ar.Grow(size - ar.RemainingBytes());
    }
    std::memcpy(ar.CurrPtr(), reinterpret_cast<const void *>(ptr), size);
    ar.Advance(size);
  }

  template <typename T>
    requires(!Container<T>)
  void Write(const T &value) {
    const auto size = sizeof(value);
    Write(&value, size);
  }

  void Write(const auto &v) {
    Write(v.size());
    using Element = typename std::remove_reference_t<decltype(v)>::value_type;
    if constexpr (requires { v.data(); } &&
                  std::is_trivially_copyable_v<Element> && !Container<Element>) {
      // The old per-element writes used these same native bytes. Keep the
      // format, but copy flat cache tables in one operation on the render thread.
      Write(v.data(), v.size() * sizeof(Element));
    } else {
      for (const auto &elem : v) {
        Write(elem);
      }
    }
  }

  void Write(const std::string &s) {
    Write(s.size());
    Write(s.c_str(), s.size());
  }

  Writer() = delete;
  explicit Writer(Archive &ar_) : ar{ar_} {}

  Archive &ar;
};

struct Reader {
  template <typename T> void Read(T *ptr, size_t size) {
    ar.Require(size);
    if (!size) {
      return;
    }
    std::memcpy(reinterpret_cast<void *>(ptr), ar.CurrPtr(), size);
    ar.Advance(size);
  }

  template <typename T>
    requires(!Container<T>)
  void Read(T &value) {
    const auto size = sizeof(value);
    Read(&value, size);
  }

  void Read(auto &v) {
    size_t num_elements{};
    Read(num_elements);
    using Element = typename std::remove_reference_t<decltype(v)>::value_type;
    constexpr size_t minimum =
        Container<Element> ? sizeof(size_t) : sizeof(Element);
    if (num_elements > ar.RemainingBytes() / minimum) {
      throw ReadError("Shader cache container length exceeds its record");
    }
    if constexpr (requires { v.data(); v.resize(size_t{}); v.max_size(); } &&
                  std::is_trivially_copyable_v<Element> && !Container<Element>) {
      if (num_elements > v.max_size() - v.size()) {
        throw ReadError("Shader cache container length exceeds capacity");
      }
      const auto start = v.size();
      v.resize(start + num_elements);
      if (num_elements) Read(v.data() + start, num_elements * sizeof(Element));
    } else {
      for (size_t i = 0; i < num_elements; ++i) {
        v.emplace_back();
        Read(v.back());
      }
    }
  }

  void Read(std::string &s) {
    size_t length{};
    Read(length);
    ar.Require(length);
    s.resize(length);
    Read(s.data(), length);
  }

  Reader() = delete;
  explicit Reader(Archive &ar_) : ar{ar_} {}

  Archive &ar;
};

} // namespace Serialization
