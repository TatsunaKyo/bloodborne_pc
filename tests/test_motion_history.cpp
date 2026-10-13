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
    assert(!CameraBounded(draw));
    auto world = draw; world.shader=ModelBatchShader;world.model_batch=7;
    assert(CameraBounded(world));
    world.model_batch=0;assert(!CameraBounded(world));
    world.shader=1;world.model_batch=7;assert(!CameraBounded(world));
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
    assert(!next.load && next.store != first.store);
    assert(!history.Prepare(draw).load && history.stats.ambiguous >= 2);
    // A unique identity still retains animated object motion.
    History unique(32);
    const auto unique_first = unique.Prepare(draw);
    unique.NextFrame();
    assert(unique.Prepare(draw).load == unique_first.store);
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
    assert(!cut.Prepare(cut_draw).load);
    assert(!cut.Prepare(cut_draw).load);
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
    gated.NextFrame();
    assert(!gated.Moving(weapon, 5));     // reordered duplicates must not look animated
    assert(!gated.Moving(weapon, 4));
    assert(ClassifyBuffer(864) == BufferRole::Other && ClassifyBuffer(416) == BufferRole::Other);
    assert(ClassifyBuffer(96) == BufferRole::SmallSkeleton &&
           ClassifyBuffer(384) == BufferRole::SmallSkeleton);
    assert(ClassifyBuffer(656) == BufferRole::Skeleton && ClassifyBuffer(64) == BufferRole::Other);

    // Hunter's Dream foliage uses 8/32 model records in one indexed draw. Culling
    // can replace or reorder those trees without changing mesh/topology/firstInstance.
    // The old key therefore reads another tree's positions. Match the ordered
    // world transforms, preserving history when only camera/material fields change.
    constexpr uint64_t tree_shader = ModelBatchShader;
    uint32_t batch_cases = 0;
    for (const uint32_t models : {1u, 2u, 4u, 8u, 16u, 32u}) {
        assert(HasModelBatch(tree_shader, models * 416));
        assert(!HasModelBatch(123, models * 416));
        std::vector<std::byte> records(models * 416);
        for (uint32_t i = 0; i < models; ++i) {
            const std::array<float,12> world{
                .295833f, 0, .634416f, 1.82819f + 4 * i,
                0, .7f, 0, -8.66246f,
                -.634416f, 0, .295833f, -38.765f - 2 * i};
            std::memcpy(records.data() + i * 416, world.data(), sizeof(world));
        }
        const auto id = ModelBatchIdentity(records);
        assert(id && *id != 0);
        auto camera_changed = records;
        for (uint32_t i = 0; i < models; ++i)
            std::fill(camera_changed.begin() + i * 416 + 48,
                      camera_changed.begin() + (i + 1) * 416, std::byte{0x5a});
        assert(ModelBatchIdentity(camera_changed) == id);
        Draw batch{.shader=tree_shader,.geometry=2,.indices=3,.topology=4,
            .index_count=30,.instances=models,.vertices={0,3}};
        History old_key(1024);
        const auto old_positions = old_key.Prepare(batch);
        old_key.NextFrame();
        assert(old_key.Prepare(batch).load == old_positions.store); // old defect reproduced

        batch.model_batch = *id;
        History matched(1024);
        auto positions = matched.Prepare(batch);
        matched.NextFrame();
        assert(matched.Prepare(batch).load == positions.store);
        for (uint32_t changed_instance = 0; changed_instance < models; ++changed_instance) {
            auto changed_records = records;
            float translation;
            const auto offset = changed_instance * 416 + 3 * sizeof(float);
            std::memcpy(&translation, changed_records.data() + offset, sizeof(float));
            translation += 20; // a different tree now occupies the same slot
            std::memcpy(changed_records.data() + offset, &translation, sizeof(float));
            const auto changed_id = ModelBatchIdentity(changed_records);
            assert(changed_id && changed_id != id);
            History replaced(1024);
            replaced.Prepare(batch);
            replaced.NextFrame();
            auto replacement = batch;
            replacement.model_batch = *changed_id;
            assert(!replaced.Prepare(replacement).load);
            ++batch_cases;
        }
        for (uint32_t other = 1; other < models; ++other) {
            auto reordered = records;
            std::swap_ranges(reordered.begin(), reordered.begin()+416,
                             reordered.begin()+other*416);
            const auto reordered_id = ModelBatchIdentity(reordered);
            assert(reordered_id && reordered_id != id);
            History reordered_history(1024);
            reordered_history.Prepare(batch);
            reordered_history.NextFrame();
            auto reordered_draw = batch;
            reordered_draw.model_batch = *reordered_id;
            const auto new_positions = reordered_history.Prepare(reordered_draw);
            assert(new_positions.store && !new_positions.load);
            reordered_history.NextFrame();
            assert(reordered_history.Prepare(reordered_draw).load == new_positions.store);
            ++batch_cases;
        }
        const History::GateKey batch_gate{.shader=tree_shader,.model_batch=*id};
        History gate(1024);
        assert(!gate.Moving(batch_gate, 1));
        gate.NextFrame();
        assert(gate.Moving(batch_gate, 2)); // same trees, updated wind palette
        auto reordered_gate=batch_gate;
        reordered_gate.model_batch=*ModelBatchIdentity(camera_changed);
        assert(reordered_gate.model_batch==batch_gate.model_batch);
        auto invalid=records;
        const float nan=std::numeric_limits<float>::quiet_NaN();
        std::memcpy(invalid.data(),&nan,sizeof(nan));
        assert(!ModelBatchIdentity(invalid));
    }
    assert(HasModelBatch(tree_shader,416) && !HasModelBatch(tree_shader,3*416));
    assert(!HasModelBatch(tree_shader,64*416) && !ModelBatchIdentity({}));
    std::printf("Instanced foliage: old mesh-only key reproduced; %u reordered/replaced batch cases rejected, stable world records retained\n",batch_cases);

    // An allocation reused on the very next draw must invalidate both the
    // cached bounds and topology, including changes inside unchanged bounds.
    IndexRangeCache ranges;
    uint32_t scans = 0;
    const IndexRangeCache::Key mesh{.address = 0x1000, .count = 3, .index_size = 2};
    const auto scan = [&] {++scans; return IndexRangeCache::Result{{4,3},99};};
    assert(ranges.Get(mesh,0,99,scan).topology==99 && scans==1);
    for (uint64_t f=1; f<=64; ++f)
        assert(ranges.Get(mesh,f,99,scan).range==(VertexRange{4,3}));
    assert(scans==1);
    const auto changed_scan=[&] {++scans;return IndexRangeCache::Result{{4,3},100};};
    const auto fresh=ranges.Get(mesh,65,100,changed_scan);
    assert(fresh.topology==100 && scans==2 && ranges.stats.stale==1);
    History reused(32);
    Draw old_mesh{.shader=1,.geometry=2,.indices=mesh.address,.topology=99,
        .index_count=3,.instances=1,.vertices={4,3}};
    assert(reused.Prepare(old_mesh).store);
    reused.NextFrame();
    old_mesh.topology=fresh.topology;
    assert(!reused.Prepare(old_mesh).load); // no previous data from another mesh
    ranges.Trim(65+IndexRangeCache::Unused+1);assert(ranges.Size()==0);

    IndexRangeCache scene;
    constexpr uint32_t meshes=4096;
    std::array<uint32_t,65> scans_per_frame{};
    for (uint64_t f=0; f<=64; ++f) {
        for (uint32_t i=0; i<meshes; ++i) {
            const IndexRangeCache::Key key{.address=0x100000+uint64_t(i)*4096,.count=384,.index_size=2};
            const uint64_t topology=i+uint64_t(f==1 && i<16)*meshes;
            scene.Get(key,f,topology,[&] {
                ++scans_per_frame[f];return IndexRangeCache::Result{{0,128},topology};
            });
        }
    }
    assert(scans_per_frame[0]==meshes && scans_per_frame[1]==16 && scans_per_frame[2]==16);
    assert(scene.stats.scans==meshes+32);
    assert(*std::max_element(scans_per_frame.begin()+3,scans_per_frame.end())==0);
    std::printf("Index content fixture: %u meshes; 16 reused allocations rejected immediately; unchanged meshes keep cached bounds\n",meshes);

    assert(JitterPhases(1920, 1920) == 8);
    assert(JitterPhases(1280, 1920) == 18);
    assert(JitterPhases(960, 1920) == 32);
    assert(JitterPhases(640, 1920) == 72);
    assert(JitterPhases(0, 1920) == 8);
    std::puts("Motion history: PASS (ranges, restart, offsets, unique matching, ambiguous instance rejection, capacity, camera cut allocations, gating, immediate index-content validation, jitter)");
}
