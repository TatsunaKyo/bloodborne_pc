// SPDX-License-Identifier: GPL-2.0-or-later
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
#include "bbport_hitch_trace.h"
#include "bbport_threads.h"
#include <condition_variable>
#include <deque>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <locale>
#include <mutex>
#include <sstream>
#include <thread>
#ifdef _WIN32
#include <windows.h>
#else
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace BbHitch::Trace {
namespace {
constexpr uint64_t FileLimit = 16 * 1024 * 1024;
uint32_t NativeThread() {
#ifdef _WIN32
    return GetCurrentThreadId();
#else
    return static_cast<uint32_t>(syscall(SYS_gettid));
#endif
}
int64_t Ns(Clock::time_point at) {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(at.time_since_epoch()).count();
}
void String(std::ostream& out, const char* text) {
    out << '"';
    for (const unsigned char* p = reinterpret_cast<const unsigned char*>(text ? text : ""); *p; ++p) {
        if (*p == '"' || *p == '\\') out << '\\' << static_cast<char>(*p);
        else if (*p < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << unsigned(*p) << std::dec;
        else out << static_cast<char>(*p);
    }
    out << '"';
}
struct Batch {
    std::string phase;
    Clock::time_point begin, end;
    std::vector<Event> events;
    uint64_t lost, dropped, sequence;
    unsigned collisions;
    bool truncated;
};
class FileExporter {
public:
    explicit FileExporter(const std::filesystem::path& path) : output{path, std::ios::binary} {
        if (!output) return;
        output.imbue(std::locale::classic());
        uint64_t qpc = 0, frequency = 0, pid = 0, base = 0;
#ifdef _WIN32
        LARGE_INTEGER counter{}, hz{};
        QueryPerformanceCounter(&counter); QueryPerformanceFrequency(&hz);
        qpc = counter.QuadPart; frequency = hz.QuadPart;
        pid = GetCurrentProcessId(); base = reinterpret_cast<uintptr_t>(GetModuleHandleW(nullptr));
#else
        pid = getpid();
#endif
        output << "{\"record\":\"clock\",\"schema\":1,\"steady_ns\":" << Ns(Clock::now())
               << ",\"qpc\":" << qpc << ",\"qpc_hz\":" << frequency << ",\"pid\":" << pid
               << ",\"module_base\":\"0x" << std::hex << base << std::dec
               << "\",\"window_limited\":true,\"maximum_bytes\":" << FileLimit << "}\n";
        output.flush();
        if (output) worker = std::thread([this] { Run(); });
    }
    bool Ready() const { return worker.joinable(); }
    void Enqueue(const char* phase, Clock::time_point begin, Clock::time_point end,
                 std::vector<Event> events, uint64_t lost, unsigned collisions, bool truncated) {
        std::scoped_lock lock{mutex};
        if (pending.size() >= 2) { ++dropped; return; }
        pending.push_back({phase, begin, end, std::move(events), lost, dropped, ++issued, collisions, truncated});
        available.notify_one();
    }
    void Flush() {
        std::unique_lock lock{mutex};
        const auto target = issued;
        finished.wait(lock, [&] { return completed >= target; });
    }
private:
    void Write(Batch& b) {
        std::sort(b.events.begin(), b.events.end(), [](const Event& a, const Event& c) { return a.start < c.start; });
        std::ostringstream s; s.imbue(std::locale::classic());
        s << "{\"record\":\"window\",\"phase\":"; String(s, b.phase.c_str());
        s << ",\"begin_ns\":" << Ns(b.begin) << ",\"end_ns\":" << Ns(b.end)
          << ",\"lost\":" << b.lost << ",\"dropped_windows\":" << b.dropped
          << ",\"collisions\":" << b.collisions << ",\"truncated\":" << (b.truncated ? "true" : "false") << ",\"events\":[";
        bool comma = false;
        for (const auto& e : b.events) {
            if (comma) s << ',';
            comma = true;
            s << "{\"stage\":"; String(s, e.stage); s << ",\"role\":"; String(s, e.role);
            s << ",\"thread\":" << e.thread << ",\"os_thread\":" << e.native_thread
              << ",\"start_ns\":" << Ns(e.start) << ",\"end_ns\":" << Ns(e.end)
              << ",\"address\":\"0x" << std::hex << e.address << std::dec << "\",\"bytes\":" << e.bytes
              << ",\"id\":" << e.id << ",\"depends_on\":" << e.dependency << '}';
        }
        s << "]}\n";
        const auto payload = s.str();
        if (static_cast<uint64_t>(output.tellp()) + payload.size() > FileLimit - 256) {
            output << "{\"record\":\"limit\",\"reason\":\"16 MiB limit\"}\n"; capped = true;
        } else output << payload;
        output.flush();
    }
    void Run() {
        BbThreads::MakeBackground();
        for (;;) {
            std::unique_lock lock{mutex};
            available.wait(lock, [&] { return !pending.empty(); });
            auto batch = std::move(pending.front()); pending.pop_front();
            batch.dropped = dropped;
            lock.unlock();
            if (!capped && output) Write(batch);
            lock.lock(); completed = batch.sequence; finished.notify_all();
        }
    }
    std::ofstream output;
    std::mutex mutex;
    std::condition_variable available, finished;
    std::deque<Batch> pending;
    uint64_t issued{}, completed{}, dropped{};
    bool capped{};
    std::thread worker;
};
FileExporter* destination{}; // process lifetime: guest threads can outlive normal teardown
}
void FlushExporter() { if (destination) destination->Flush(); }
void InstallExporter() {
    static const bool once = [] {
        if (!Enabled()) return false;
#ifdef _WIN32
        const auto* path = _wgetenv(L"BB_HITCH_TRACE_PATH");
#else
        const auto* path = std::getenv("BB_HITCH_TRACE_PATH");
#endif
        if (!path || !*path) return false;
        try {
            auto* file = new FileExporter{std::filesystem::path{path}};
            if (!file->Ready()) { delete file; std::puts("CPU dependency timeline unavailable"); return false; }
            destination = file;
            native_thread_provider.store(&NativeThread, std::memory_order_release);
            exporter.store(+[](const char* phase, Clock::time_point begin, Clock::time_point end,
                               std::vector<Event> events, uint64_t lost, unsigned collisions, bool truncated) {
                destination->Enqueue(phase, begin, end, std::move(events), lost, collisions, truncated);
            }, std::memory_order_release);
            std::atexit(&FlushExporter);
            std::puts("CPU dependency timeline active: bounded windows, request links and native thread IDs");
            return true;
        } catch (...) { std::puts("CPU dependency timeline unavailable"); return false; }
    }();
    (void)once;
}
} // namespace BbHitch::Trace
