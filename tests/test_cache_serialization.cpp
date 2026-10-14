// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include <algorithm>
#include <bit>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <deque>
#include <fstream>
#include <iterator>
#include <limits>
#include <string>
#include <vector>
#include TEST_SERDES_HEADER

struct Pod { std::uint32_t index, bits; std::uint64_t flags; };
static_assert(sizeof(Pod) == 16 && std::is_trivially_copyable_v<Pod>);

// Counts the real template's container operations without replacing its IO.
template <typename T> struct CountedVector {
    using value_type = T;
    using iterator = typename std::vector<T>::iterator;
    std::vector<T> values;
    static inline unsigned data_calls{}, resizes{}, emplaces{};
    auto begin() { return values.begin(); }
    auto end() { return values.end(); }
    auto begin() const { return values.begin(); }
    auto end() const { return values.end(); }
    auto size() const { return values.size(); }
    auto max_size() const { return values.max_size(); }
    auto data() { ++data_calls; return values.data(); }
    auto data() const { ++data_calls; return values.data(); }
    void resize(std::size_t n) { ++resizes; values.resize(n); }
    void emplace_back() { ++emplaces; values.emplace_back(); }
    auto& back() { return values.back(); }
    static void Reset() { data_calls = resizes = emplaces = 0; }
};

struct Data {
    std::vector<Pod> flat;
    std::vector<float> floats;
    std::vector<std::vector<std::uint16_t>> nested{{}, {7, 8, 9}, {}, {65535}};
    std::vector<std::string> names{"", "shader", std::string("a\0b", 3)};
    std::deque<std::uint32_t> noncontiguous{3, 5, 8, 13};
    std::string text = std::string("cache\0metadata", 14);
    CountedVector<std::uint32_t> counted;
    Data() {
        for (std::uint32_t n = 0; n < 32768; ++n) {
            flat.push_back({n, n * 13, std::uint64_t(n) * 0x1122334455ull});
            counted.values.push_back(n * 17);
        }
        // Preserve negative zero, infinities and NaN payloads as raw cache bytes.
        for (auto bits : {0u, 0x80000000u, 0x3f800000u, 0x7f800000u, 0x7fc01234u})
            floats.push_back(std::bit_cast<float>(bits));
    }
};

static void Write(const std::string& path) {
    Data expected;
    Serialization::Archive ar;
    Serialization::Writer writer(ar);
    const std::uint64_t tag = 0x1020304050607080ull;
    writer.Write(tag);
    writer.Write(expected.flat);
    writer.Write(expected.floats);
    writer.Write(expected.nested);
    writer.Write(expected.names);
    writer.Write(expected.noncontiguous);
    writer.Write(expected.text);
    CountedVector<std::uint32_t>::Reset();
    writer.Write(expected.counted);
    assert(CountedVector<std::uint32_t>::data_calls == FAST_PATH);
    const auto bytes = ar.TakeOff();
    std::ofstream file(path, std::ios::binary);
    file.write(reinterpret_cast<const char*>(bytes.data()), bytes.size());
    assert(file.good());
}

static void Read(const std::string& path) {
    Data expected;
    std::ifstream file(path, std::ios::binary);
    assert(file.good());
    std::vector<u8> bytes{std::istreambuf_iterator<char>(file), {}};
    Serialization::Archive ar(std::move(bytes));
    Serialization::Reader reader(ar);
    std::uint64_t tag{};
    std::vector<Pod> flat{{99, 98, 97}};
    std::vector<float> floats;
    std::vector<std::vector<std::uint16_t>> nested;
    std::vector<std::string> names;
    std::deque<std::uint32_t> noncontiguous;
    std::string text = "overwrite this";
    CountedVector<std::uint32_t> counted;
    counted.values.push_back(42);
    reader.Read(tag); reader.Read(flat); reader.Read(floats); reader.Read(nested);
    reader.Read(names); reader.Read(noncontiguous); reader.Read(text);
    CountedVector<std::uint32_t>::Reset();
    reader.Read(counted);
    assert(tag == 0x1020304050607080ull && ar.IsEoS());
    assert(flat.size() == expected.flat.size() + 1 && flat[0].index == 99);
    assert(std::memcmp(flat.data() + 1, expected.flat.data(), expected.flat.size() * sizeof(Pod)) == 0);
    assert(floats.size() == expected.floats.size());
    assert(std::memcmp(floats.data(), expected.floats.data(), floats.size() * sizeof(float)) == 0);
    assert(nested == expected.nested && names == expected.names);
    assert(noncontiguous == expected.noncontiguous && text == expected.text);
    assert(counted.values.size() == expected.counted.values.size() + 1 && counted.values[0] == 42);
    assert(std::equal(expected.counted.values.begin(), expected.counted.values.end(), counted.values.begin() + 1));
    assert(CountedVector<std::uint32_t>::resizes == FAST_PATH);
    assert(CountedVector<std::uint32_t>::emplaces == (FAST_PATH ? 0 : expected.counted.size()));
    std::printf("PASS: %s serializer cross-reads flat/nested containers, strings, noncontiguous storage, exact float bits and append semantics.\n", FAST_PATH ? "bulk" : "R35");
}

static void Malformed() {
    for (const auto length : {std::size_t(3), std::numeric_limits<std::size_t>::max()}) {
        Serialization::Archive ar;
        Serialization::Writer writer(ar);
        writer.Write(length);
        const Pod truncated[2]{};
        writer.Write(truncated, sizeof(truncated));
        auto bytes = ar.TakeOff();
        Serialization::Archive input(std::move(bytes));
        Serialization::Reader reader(input);
        std::vector<Pod> out{{9, 8, 7}};
        bool rejected = false;
        try { reader.Read(out); } catch (const Serialization::ReadError&) { rejected = true; }
        assert(rejected && out.size() == 1 && out.front().index == 9);
    }
    // Empty containers add their length prefix and leave existing content intact.
    Serialization::Archive ar;
    Serialization::Writer writer(ar);
    writer.Write(std::vector<std::uint64_t>{});
    Serialization::Archive input(ar.TakeOff());
    Serialization::Reader reader(input);
    std::vector<std::uint64_t> out{11};
    reader.Read(out);
    assert(out == std::vector<std::uint64_t>{11} && input.IsEoS());
}

int main(int argc, char** argv) {
    assert(argc == 3);
    Malformed();
    if (std::string(argv[1]) == "write") Write(argv[2]);
    else { assert(std::string(argv[1]) == "read"); Read(argv[2]); }
}
