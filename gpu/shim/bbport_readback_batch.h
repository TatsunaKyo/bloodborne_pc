// SPDX-License-Identifier: GPL-2.0-or-later
// TatsunaKyo: bounded, synchronous readback groups. No write survives page retirement.
#pragma once
#include <cstddef>
#include <functional>
#include <utility>
#include <vector>

namespace BbReadback {
class Batch {
public:
    explicit Batch(std::function<void()> wait) : wait(std::move(wait)) {}
    void Prepare(std::size_t size) {
        if (!copies.empty() && (bytes + size > 32u*1024*1024 || copies.size() >= 16)) Flush();
    }
    void Copy(std::size_t size, std::function<void()> copy) {
        bytes += size; copies.push_back(std::move(copy));
    }
    void Retire(std::function<void()> retire) { retirements.push_back(std::move(retire)); }
    void Flush() {
        if (copies.empty()) return;
        wait(); ++waits;
        // Complete ALL backing writes before ANY page becomes reusable by the guest.
        for (auto& copy : copies) copy();
        copies.clear(); bytes = 0;
        for (auto& retire : retirements) retire();
        retirements.clear();
    }
    unsigned Waits() const { return waits; }
private:
    std::function<void()> wait;
    std::vector<std::function<void()>> copies, retirements;
    std::size_t bytes{};
    unsigned waits{};
};
}
