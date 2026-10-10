// SPDX-License-Identifier: GPL-2.0-or-later
// Standalone CPU regression checks: no game, Vulkan device or window required.
#include <array>
#include <cassert>
#include <cstdio>
#include "gpu/shadps4/video_core/renderer_vulkan/motion_history.h"

using namespace Vulkan::Motion;

int main() {
    const std::array<uint16_t, 5> indices{1000, 1007, 1002, 1007, UINT16_MAX};
    const auto range = IndexedRange(std::span(indices), -900, true);
    assert(range.first == 100 && range.count == 8);
    assert(IndexedRange(std::span(indices), -1001, true).count == 0);
    assert(IndexedRange(std::span(indices), 0, false).count == 64536);
    const std::array<uint32_t, 3> large{100000, 100003, UINT32_MAX};
    assert(IndexedRange(std::span(large), 7, true).count == 4);
    assert(IndexedRange(std::span(large), INT32_MAX, true).count == 0);
    const std::array<uint16_t, 1> restart{UINT16_MAX};
    assert(IndexedRange(std::span(restart), 0, true).count == 0);
    assert(IndexedRange(std::span<const uint16_t>{}, 0, false).count == 0);

    Draw draw{.shader = 1, .geometry = 2, .indices = 3, .topology = 4,
              .index_count = 5, .instances = 2, .first_instance = 100,
              .vertices = range};
    History history(32);
    history.NextFrame();
    const auto first = history.Prepare(draw);
    const auto duplicate = history.Prepare(draw);
    assert(first.store && !first.load && first.first_vertex == 100);
    assert(first.first_instance == 100 && first.instances == 2);
    assert(duplicate.store == first.store + 16); // shared geometry, different draw
    assert(history.Used() == 32); // firstInstance must NOT multiply the allocation
    assert(!history.Prepare(draw).store && history.stats.exhausted == 1);
    history.NextFrame();
    const auto next = history.Prepare(draw);
    assert(next.load == first.store && next.store != first.store);
    assert(history.Prepare(draw).load == duplicate.store);
    history.NextFrame(); // a missing frame invalidates the match
    history.NextFrame();
    assert(!history.Prepare(draw).load);

    // A changed index buffer may reference formerly unused holes inside the same min/max.
    // Do not accept that history merely because its addresses/counts stayed the same.
    history.NextFrame();
    auto changed = draw;
    changed.topology++;
    assert(!history.Prepare(changed).load);

    // A camera cut after reservations must not rewind the GPU allocation cursor.
    History cut(128);
    Draw cut_draw{.shader=9, .geometry=10, .instances=1, .vertices={0, 8}};
    cut.NextFrame();
    const auto old = cut.Prepare(cut_draw);
    cut.NextFrame();
    const auto before_cut = cut.Prepare(cut_draw);
    assert(before_cut.load == old.store);
    cut.DiscardPrevious();
    assert(cut.Used() == 8);
    const auto after_cut = cut.Prepare(cut_draw);
    assert(!after_cut.load && after_cut.store == before_cut.store + 8);
    cut.NextFrame();
    assert(cut.Prepare(cut_draw).load == before_cut.store);
    assert(cut.Prepare(cut_draw).load == after_cut.store);
    changed = draw;
    changed.first_instance++;
    assert(!history.Prepare(changed).load);
    history.NextFrame();
    changed = draw;
    changed.vertices.first++;
    assert(!history.Prepare(changed).load);

    History overflow(32);
    draw.vertices.first = 0;
    draw.vertices.count = INT32_MAX;
    draw.instances = UINT32_MAX;
    draw.first_instance = 0;
    assert(!overflow.Prepare(draw).store);
    assert(overflow.stats.exhausted == 1);
    draw.first_instance = 10;
    assert(!overflow.Prepare(draw).store && overflow.stats.invalid == 1);
    draw.first_instance = 0;
    draw.vertices.first = INT32_MAX;
    draw.vertices.count = 2;
    assert(!overflow.Prepare(draw).store && overflow.stats.invalid == 2);

    // Small skeletons: history only while the bone palette changes (weapon spinning).
    History gated(1024);
    const History::GateKey weapon{.shader = 7, .index_count = 3, .instances = 1};
    const auto frame = [&](uint64_t palette) {
        gated.NextFrame();
        return gated.Moving(weapon, palette);
    };
    assert(!gated.Moving(weapon, 1) && gated.stats.still == 1); // first sight
    assert(!frame(1));                    // same bones: camera motion
    assert(frame(2) && frame(3));         // spinning
    assert(!frame(3));                    // stopped
    gated.NextFrame();
    gated.NextFrame();
    assert(!gated.Moving(weapon, 4));     // after a skipped frame: no comparison
    assert(!gated.Moving(weapon, 5));     // second occurrence of the same draw
    assert(ClassifyBuffer(864) == BufferRole::Other && ClassifyBuffer(416) == BufferRole::Other);
    assert(ClassifyBuffer(96) == BufferRole::SmallSkeleton &&
           ClassifyBuffer(384) == BufferRole::SmallSkeleton);
    assert(ClassifyBuffer(656) == BufferRole::Skeleton && ClassifyBuffer(64) == BufferRole::Other);

    // Index ranges: reused between full scans, rescanned every Revalidate frames, trimmed.
    IndexRangeCache ranges;
    uint32_t scans = 0;
    const IndexRangeCache::Key mesh{.address = 0x1000, .count = 3, .index_size = 2};
    const auto scan = [&] {
        ++scans;
        return IndexRangeCache::Result{{4, 3}, 99};
    };
    assert(ranges.Get(mesh, 0, scan).topology == 99 && scans == 1);
    uint64_t first_check = 0;
    for (uint64_t f = 1; f <= IndexRangeCache::Revalidate; ++f) {
        assert(ranges.Get(mesh, f, scan).range == (VertexRange{4, 3}));
        if (scans == 2 && first_check == 0) first_check = f;
    }
    assert(first_check > 0 && first_check <= IndexRangeCache::Revalidate && scans == 2);
    const auto changed_scan = [&] {
        ++scans;
        return IndexRangeCache::Result{{4, 4}, 100};
    };
    assert(ranges.Get(mesh, first_check + IndexRangeCache::Revalidate, changed_scan).topology == 100);
    assert(scans == 3 && ranges.stats.stale == 1);
    ranges.Trim(first_check + IndexRangeCache::Revalidate + IndexRangeCache::Unused + 1);
    assert(ranges.Size() == 0);

    // Meshes loaded together must no longer all revalidate in one periodic frame.
    IndexRangeCache scene;
    constexpr uint32_t meshes = 4096;
    std::array<uint64_t, meshes> last_checked{};
    std::array<uint32_t, 65> scans_per_frame{};
    for (uint64_t f = 0; f <= 64; ++f) {
        for (uint32_t i = 0; i < meshes; ++i) {
            const IndexRangeCache::Key key{.address=0x100000+uint64_t(i)*4096,
                .count=384, .index_size=2};
            scene.Get(key, f, [&] {
                assert(f - last_checked[i] <= IndexRangeCache::Revalidate);
                last_checked[i] = f;
                ++scans_per_frame[f];
                return IndexRangeCache::Result{{0, 128}, i};
            });
        }
    }
    const auto peak = *std::max_element(scans_per_frame.begin()+1, scans_per_frame.end());
    assert(scans_per_frame[0] == meshes && scene.stats.scans == meshes * 3);
    assert(peak < meshes / 8);
    std::printf("Index verification fixture: %u meshes; periodic peak %u scans/frame (previous policy: %u)\n",
                meshes, peak, meshes);

    assert(JitterPhases(1920, 1920) == 8);
    assert(JitterPhases(1280, 1920) == 18);
    assert(JitterPhases(960, 1920) == 32);
    assert(JitterPhases(640, 1920) == 72);
    assert(JitterPhases(0, 1920) == 8);
    std::puts("Motion history: PASS (ranges, restart, offsets, matching, capacity, camera cut allocations, gating, staggered index cache, jitter)");
}
