// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "common/logging/log.h"
#include "common/serdes.h"
#include "core/emulator_settings.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include <array>
#include <functional>
#include <iostream>
#include <optional>
namespace Serialization {
constexpr u32 PipelineKeyVersion = 5;
}
namespace Shader {
struct Profile {
  u32 gpu = 1;
  bool operator==(const Profile &) const = default;
};
} // namespace Shader
namespace Storage {
enum class BlobType { ShaderProfile, PipelineKey };
struct DataBase {
  std::vector<u8> profile;
  std::vector<std::vector<u8>> keys;
  unsigned cleared = 0, finished = 0, saved = 0;
  static DataBase &Instance() {
    static DataBase db;
    return db;
  }
  void Open() {}
  void Load(BlobType, const char *, std::vector<u8> &data) { data = profile; }
  void Clear() {
    ++cleared;
    keys.clear();
  }
  void FinishPreload() { ++finished; }
  void Save(BlobType, const char *, std::vector<u8> &&data) {
    ++saved;
    profile = std::move(data);
  }
  void ForEachBlob(BlobType, const std::function<void(std::vector<u8> &&)> &f) {
    for (const auto &key : keys)
      f(std::vector<u8>(key));
  }
};
} // namespace Storage
namespace Vulkan {
struct PipelineCache {
  Shader::Profile profile;
  struct Selection {
    std::array<int,6> runtime_infos{};
    std::array<const int *, 6> infos{};
    std::array<void *, 6> modules{};
    std::optional<int> fetch_shader;
  } sel;
  unsigned loads = 0, successful = 0;
  struct Queue { void Drain() {} };
  Queue* build_queue=nullptr;
  void LoadDriverCache() {}
  void SaveDriverCache() {}
  void PublishPreloads() {}
  void WarmUp();
  bool LoadComputePipeline(Serialization::Archive &ar) { return Load(ar); }
  bool LoadGraphicsPipeline(Serialization::Archive &ar) { return Load(ar); }
  bool Load(Serialization::Archive &ar) {
    if (sel.infos[0] || sel.modules[0] || sel.fetch_shader)
      throw std::runtime_error("stale preload selection");
    ++loads;
    u32 action = 0;
    Serialization::Reader reader(ar);
    reader.Read(action);
    static int stage = 1;
    sel.infos[0] = &stage;
    sel.modules[0] = &stage;
    sel.fetch_shader = 1;
    if (action == 1)
      throw CacheLoadError("driver rejected pipeline");
    if (action == 2)
      throw Serialization::ReadError("invalid shader metadata");
    if (action == 3)
      return false;
    ++successful;
    return true;
  }
};
#include "production_warmup.inc"
} // namespace Vulkan
namespace {
void Check(bool v, const char *m) {
  if (!v)
    throw std::runtime_error(m);
}
std::vector<u8> Key(u32 version, u32 kind, u32 action = 0) {
  Serialization::Archive ar;
  Serialization::Writer writer(ar);
  writer.Write(version);
  writer.Write(kind);
  writer.Write(action);
  return ar.TakeOff();
}
std::vector<u8> Profile(u32 gpu) {
  std::vector<u8> data(sizeof(Shader::Profile));
  Shader::Profile p{gpu};
  std::memcpy(data.data(), &p, sizeof(p));
  return data;
}
} // namespace
int main() {
  try {
    auto &db = Storage::DataBase::Instance();
    for (int mode = 0; mode < 4; ++mode) {
      db = {};
      db.keys = {Key(5, 0)};
      if (mode == 1)
        db.profile = {1, 2};
      if (mode == 2)
        db.profile = Profile(9);
      if (mode == 3)
        db.profile = Profile(1);
      Vulkan::PipelineCache cache;
      cache.WarmUp();
      if (mode < 3)
        Check(db.cleared == 1 && db.saved == 1 && db.keys.empty() &&
                  cache.loads == 0 && db.profile == Profile(1),
              "missing/corrupt/incompatible profile kept old records");
      else
        Check(db.cleared == 0 && db.saved == 0 && cache.successful == 1,
              "compatible cache not preloaded");
      Check(db.finished == 1, "cache not made writable");
    }
    db = {};
    db.profile = Profile(1);
    db.keys = {std::vector<u8>{1}, Key(5, 0, 1), Key(5, 1, 2), Key(5, 0, 3),
               Key(4, 0),          Key(5, 99),   Key(5, 1),    Key(5, 0)};
    Vulkan::PipelineCache cache;
    cache.sel.fetch_shader = 44;
    cache.WarmUp();
    Check(cache.loads == 5 && cache.successful == 2,
          "damaged preload stopped later valid pipelines");
    Check(db.finished == 1 && !cache.sel.fetch_shader && !cache.sel.infos[0] &&
              !cache.sel.modules[0],
          "failed preload left selection state");
    std::cout
        << "PASS actual WarmUp: missing/corrupt/incompatible profiles rebuild; "
           "compatible profile reused\n"
        << "PASS actual WarmUp: truncated/unknown/stale/rejected pipelines "
           "skipped; later valid records preloaded; selection reset\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << "FAIL: " << e.what() << '\n';
    return 1;
  }
}
