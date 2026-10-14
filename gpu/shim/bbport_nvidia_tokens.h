// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <array>
#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <utility>

namespace BbNvidia {

// Streamline owns the native token. This lease keeps its ring slot reserved
// through simulation, queued flips and the corresponding Present call.
struct FrameToken {
    void* native{};
    uint32_t index{};
};
using Token = std::shared_ptr<const FrameToken>;

template<size_t Capacity>
class TokenPool {
public:
    static_assert(Capacity > 0);

    // The caller's NVIDIA mutex serializes allocation and the SDK calls. Token
    // destruction only notifies; it must also work while that mutex is held.
    template<class Continue>
    bool WaitAvailable(std::unique_lock<std::mutex>& lock, Continue proceed) {
        while (!Available() && proceed()) {
            const auto epoch=state->epoch.load();
            if (Available() || !proceed()) continue;
            // The last owner can disappear outside the allocation mutex. An
            // atomic epoch avoids losing that notification between check/wait.
            lock.unlock();
            state->epoch.wait(epoch);
            lock.lock();
        }
        return proceed() && Available();
    }

    template<class Create>
    Token Acquire(uint32_t index, Create create) {
        if (!Available()) return {};
        auto* value = new FrameToken{nullptr,index};
        Token token(value, [notify = state](const FrameToken* p) {
            delete p;
            notify->Notify();
        });
        // Allocate host ownership before asking SL to advance its native ring.
        // A host allocation failure must not desynchronize the two rings.
        value->native = create(index);
        if (!value->native) return {};
        slots[next] = token;
        next = (next + 1) % Capacity;
        return token;
    }

    bool Available() const { return slots[next].expired(); }
    void Notify() { state->Notify(); }

private:
    struct State {
        std::atomic<uint64_t> epoch{};
        void Notify() { ++epoch;epoch.notify_all(); }
    };
    std::shared_ptr<State> state = std::make_shared<State>();
    std::array<std::weak_ptr<const FrameToken>, Capacity> slots;
    size_t next{};
};

} // namespace BbNvidia
