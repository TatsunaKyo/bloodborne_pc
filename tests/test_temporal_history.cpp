// SPDX-License-Identifier: GPL-2.0-or-later
// Production camera-history policy and sampler bias, without a GPU or game image.
#include <cassert>
#include <cstdio>
#include <limits>
#include "gpu/shadps4/video_core/renderer_vulkan/temporal_history.h"

using namespace Vulkan::Motion;

static CameraSample Camera(float x = 0, float angle = 0) {
    CameraSample c;
    const float s = std::sin(angle), z = std::cos(angle);
    c.inv_view = {z, 0, s, x, 0, 1, 0, 0, -s, 0, z, 0};
    c.view = {z, 0, -s, -z*x, 0, 1, 0, 0, s, 0, z, -s*x};
    c.proj = {1.1f, 1.9f, 1.000033f, -0.1000033f};
    c.valid = true;
    return c;
}

int main() {
    // A submitted draw owns its camera snapshot even if the guest rewrites the
    // same allocation before the recording thread processes that draw.
    std::array<float,216> guest{};
    const auto original = Camera(2);
    guest[0]=3000;guest[1]=1.f/3000;guest[4]=1920;guest[5]=1080;
    std::copy(original.view.begin(),original.view.end(),guest.begin()+8);
    std::copy(original.inv_view.begin(),original.inv_view.end(),guest.begin()+180);
    guest[52]=original.proj[0];guest[57]=original.proj[1];guest[62]=original.proj[2];guest[63]=original.proj[3];
    const auto submitted = guest;
    guest[183]=1000;guest[4]=3840;
    const auto decoded=DecodeSceneCamera(submitted);
    assert(decoded && decoded->camera.inv_view==original.inv_view && decoded->size[0]==1920);
    assert(DecodeSceneCamera(guest)->camera.inv_view!=decoded->camera.inv_view);
    assert(!DecodeSceneCamera(std::span(submitted).first(215)));
    guest[4]=std::numeric_limits<float>::quiet_NaN();assert(!DecodeSceneCamera(guest));
    guest=submitted;guest[1]=0;assert(!DecodeSceneCamera(guest));
    CameraHistory history;
    assert(history.NeedsCamera());
    assert(history.Capture(Camera()) && history.Reset());
    assert(history.current.valid && history.previous.valid);
    assert(history.current.inv_view == history.previous.inv_view);
    assert(!history.Capture(Camera(100))); // later constants within the same pass are ignored
    history.EndFrame();
    assert(history.NeedsCamera() && !history.Reset());
    for (int i = 1; i <= 120; ++i) {
        const auto sample = Camera(i*0.02f, i*0.01f);
        assert(history.Capture(sample) && !history.Reset());
        assert(history.previous.inv_view != history.current.inv_view);
        history.EndFrame();
    }
    auto sample = history.current;
    sample.proj[0] *= 1.01f;
    sample.proj[1] *= 1.01f;
    assert(history.Capture(sample) && !history.Reset()); // smooth zoom
    history.EndFrame();
    sample.inv_view[3] += 12;
    assert(history.Capture(sample) && history.Reset()); // teleport
    assert(history.previous.inv_view == sample.inv_view);
    history.EndFrame();
    assert(history.Capture(sample) && !history.Reset()); // reset is not sticky
    history.EndFrame();
    const auto turn = Camera(sample.inv_view[3], 3.2f);
    assert(history.Capture(turn) && history.Reset()); // 114-degree snap
    history.EndFrame();
    sample = turn;
    sample.proj[1] *= 1.4f;
    assert(history.Capture(sample) && history.Reset()); // abrupt FOV cut
    history.EndFrame();
    assert(history.Capture(sample, true) && history.Reset()); // resized input
    history.EndFrame();
    history.Invalidate();
    assert(!history.current.valid && !history.previous.valid);
    assert(history.Capture(sample) && history.Reset()); // provider/quality change
    history.EndFrame();
    history.EndFrame(); // menu/loading: no camera this frame
    assert(!history.current.valid);
    assert(history.Capture(sample) && history.Reset());
    history.EndFrame();
    auto invalid = sample;
    invalid.inv_view[3] = std::numeric_limits<float>::quiet_NaN();
    assert(!history.Capture(invalid) && history.NeedsCamera() && history.Reset());
    assert(!history.current.valid && !history.previous.valid);
    assert(history.Capture(sample) && history.Reset()); // a later valid pass can recover
    history.EndFrame();
    invalid = sample;
    invalid.proj[0] = std::numeric_limits<float>::infinity();
    assert(!history.Capture(invalid));
    invalid = sample;
    invalid.proj[1] = 0;
    assert(!ValidCamera(invalid));
    invalid = sample;
    invalid.inv_view.fill(0);
    assert(!ValidCamera(invalid));
    auto inverted_y = Camera();
    inverted_y.proj[1] = -inverted_y.proj[1];
    assert(ValidCamera(inverted_y)); // preserve the projection's coordinate convention
    assert(CameraDiscontinuity(Camera(), inverted_y));

    // Slow rotations, including crossing +-pi, do not look like a cut.
    assert(!CameraDiscontinuity(Camera(0, 3.13f), Camera(0, -3.13f)));
    assert(!CameraDiscontinuity(Camera(), Camera(9.9f, 1.5f)));
    assert(CameraDiscontinuity(Camera(), Camera(10)));

    // A preliminary camera must not replace the completed main-scene baseline.
    CameraHistory passes;
    assert(passes.Capture(Camera(2)));
    passes.EndFrame();
    passes.BeginPass();
    assert(passes.Capture(Camera(100)) && passes.Reset());
    passes.BeginPass();
    assert(passes.NeedsCamera() && !passes.current.valid);
    assert(passes.Capture(Camera(2.1f)) && !passes.Reset());
    assert(passes.previous.inv_view == Camera(2).inv_view);
    assert(!passes.Capture(Camera(200)));
    passes.EndFrame();
    passes.BeginPass();
    assert(passes.Capture(Camera(100)));
    passes.BeginPass(); // no valid camera for the final depth: never pair with the first
    passes.EndFrame();
    assert(!passes.current.valid && !passes.previous.valid);
    assert(passes.Capture(Camera(2.2f)) && passes.Reset());

    for (float x : {-960.f,960.f}) for (float y : {-540.f,540.f}) {
        const auto camera=DecodeSceneCamera(submitted,x,y);
        assert(camera && camera->camera.proj[0] == std::copysign(1.f,x)*submitted[52]);
        assert(camera->camera.proj[1] == -std::copysign(1.f,y)*submitted[57]);
    }
    assert(!DecodeSceneCamera(submitted,0,540));
    assert(!DecodeSceneCamera(submitted,960,std::numeric_limits<float>::infinity()));

    MipBiasCache bias;
    assert(bias.Get(0, 0) == 0 && bias.Get(0, 3840) == 0);
    assert(std::abs(bias.Get(1920, 3840) + 1.0f) < 1e-6f);
    for (int i = 0; i < 10000; ++i) assert(bias.Get(1920, 3840) == -1.0f);
    assert(std::abs(bias.Get(1280, 3840) + 1.5849625f) < 1e-6f);
    assert(bias.Get(3840, 3840) == 0 && bias.Get(3840, 1920) == 0);
    assert(bias.Get(1920, 3840) == -1.0f);
    std::puts("Temporal history: PASS (submitted camera snapshot, bounds, smooth motion/FOV, cuts, resize, loading, invalid data, recovery, cached mip bias)");
}
