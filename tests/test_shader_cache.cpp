// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
#include "common/cache_blob.h"
#include "common/logging/log.h"
#include "common/path_util.h"
#include "common/serdes.h"
#include "shader_recompiler/motion_address.h"
#include "video_core/cache_storage.h"
#include "video_core/renderer_vulkan/vk_shader_util.h"
#include <array>
#include <atomic>
#include <chrono>
#include <fstream>
#include <iostream>
#include <limits>
#include <thread>

namespace {
std::filesystem::path root;
std::atomic_bool hold_worker{};
void Check(bool condition, const char *message) {
  if (!condition)
    throw std::runtime_error(message);
}
template <class Exception, class F> void Reject(F &&operation) {
  bool rejected = false;
  try {
    operation();
  } catch (const Exception &) {
    rejected = true;
  }
  Check(rejected, "invalid input accepted");
}
void Write(const std::filesystem::path &path, std::span<const u8> data) {
  std::ofstream out(path, std::ios::binary);
  out.write(reinterpret_cast<const char *>(data.data()), data.size());
  Check(bool(out), "fixture write failed");
}
std::vector<u32> Spirv() {
  return {0x07230203, 0x10000, 0, 8, 0, 0x3000e, 0, 1, 0x4000f, 5, 1, 0};
}
void Serdes() {
  Serialization::Archive ar;
  Serialization::Writer writer(ar);
  const std::vector<std::string> words{"", "hunter", "workshop"};
  writer.Write(u32{23});
  writer.Write(words);
  writer.Write(std::vector<u32>{1, 2, 3});
  auto data = ar.TakeOff();
  const auto *original = data.data();
  Serialization::Archive input(std::move(data));
  Check(input.CurrPtr() == original, "archive copied payload");
  Serialization::Reader reader(input);
  u32 revision{};
  std::vector<std::string> result;
  std::vector<u32> nums;
  reader.Read(revision);
  reader.Read(result);
  reader.Read(nums);
  Check(revision == 23 && result == words &&
            nums == std::vector<u32>({1, 2, 3}) && input.IsEoS(),
        "serdes roundtrip");
  for (size_t count = 0; count < 4; ++count) {
    Serialization::Archive bad{std::vector<u8>(count)};
    Serialization::Reader r(bad);
    Reject<Serialization::ReadError>([&] {
      u32 v;
      r.Read(v);
    });
  }
  for (int kind = 0; kind < 3; ++kind) {
    Serialization::Archive huge;
    Serialization::Writer w(huge);
    w.Write(std::numeric_limits<size_t>::max());
    auto bytes = huge.TakeOff();
    Serialization::Archive bad(std::move(bytes));
    Serialization::Reader r(bad);
    Reject<Serialization::ReadError>([&] {
      if (kind == 0) {
        std::string value;
        r.Read(value);
      }
      if (kind == 1) {
        std::vector<u32> value;
        r.Read(value);
      }
      if (kind == 2) {
        std::vector<std::string> value;
        r.Read(value);
      }
    });
  }
  Serialization::Archive empty;
  Serialization::Reader r(empty);
  r.Read(static_cast<u8 *>(nullptr), 0);
  Reject<Serialization::ReadError>(
      [&] { empty.Advance(std::numeric_limits<size_t>::max()); });
  std::cout << "PASS production deserialization: truncation, allocation "
               "bounds, ownership and empty records\n";
}
void Blobs() {
  const std::string known = "123456789";
  Check(Storage::Blob::Checksum(std::span(
            reinterpret_cast<const u8 *>(known.data()), known.size())) ==
            0xcbf43926,
        "CRC known answer");
  for (u32 kind = 0; kind < 4; ++kind) {
    const std::vector<u8> payload{1, 2, 3, 4, 5};
    auto bytes = Storage::Blob::Encode(kind, payload);
    std::span<const u8> decoded;
    Check(Storage::Blob::Decode(kind, bytes, decoded) &&
              std::ranges::equal(decoded, payload),
          "wrapped roundtrip");
    Check(Storage::Blob::Decode(kind, payload, decoded) &&
              std::ranges::equal(decoded, payload),
          "legacy read");
    for (size_t size = 1; size < bytes.size(); ++size)
      Check(!Storage::Blob::Decode(kind, std::span(bytes).first(size), decoded),
            "truncation accepted");
    for (size_t index : {size_t(8), size_t(12), size_t(16), size_t(24),
                         size_t(28), bytes.size() - 1}) {
      auto corrupt = bytes;
      corrupt[index] ^= 0x80;
      Check(!Storage::Blob::Decode(kind, corrupt, decoded),
            "damaged record accepted");
    }
    Check(!Storage::Blob::Decode((kind + 1) % 4, bytes, decoded),
          "wrong kind accepted");
  }
  auto code = Spirv();
  Check(Storage::Blob::WellFormedSpirv(code), "valid SPIR-V rejected");
  for (size_t i : {size_t(0), size_t(1), size_t(3), size_t(4), size_t(5)}) {
    auto bad = code;
    bad[i] = i == 4 ? 1 : 0;
    Check(!Storage::Blob::WellFormedSpirv(bad), "malformed SPIR-V accepted");
  }
  auto bad = code;
  bad[5] = 0xffff000e;
  Check(!Storage::Blob::WellFormedSpirv(bad), "SPIR-V overrun accepted");
  std::cout << "PASS checksummed records, legacy records and bounded SPIR-V "
               "structure\n";
}
void ShaderTest() {
  auto code = Spirv();
  vk::calls = 0;
  vk::next_result = vk::Result::eSuccess;
  Check(Vulkan::CompileSPV(code, vk::Device{}, true) != nullptr &&
            vk::calls == 1,
        "cached shader not passed to driver");
  auto bad = code;
  bad[5] = 0;
  Reject<Vulkan::CacheLoadError>(
      [&] { Vulkan::CompileSPV(bad, vk::Device{}, true); });
  Check(vk::calls == 1, "bad cached shader reached driver");
  vk::next_result = vk::Result::eErrorUnknown;
  Reject<Vulkan::CacheLoadError>(
      [&] { Vulkan::CompileSPV(code, vk::Device{}, true); });
  Reject<std::runtime_error>([&] { Vulkan::CompileSPV(code, vk::Device{}); });
  vk::next_result = vk::Result::eSuccess;
  std::cout << "PASS actual CompileSPV: malformed/rejected cache recovers; "
               "fresh shader errors stay strict\n";

  namespace Motion = Shader::MotionAddress;
  auto portable = Spirv();
  portable.insert(portable.end(), {0x40015, 2, 64, 0});
  for (const auto& [id, address] : std::array<std::pair<u32, u64>, 3>{{
           {3, Motion::Params}, {4, Motion::ParamsTail}, {5, Motion::Positions}}}) {
    portable.insert(portable.end(), {0x5002b, 2, id, u32(address), u32(address >> 32)});
  }
  const auto original = portable;
  const auto before = vk::calls;
  Motion::params_address = Motion::positions_address = 0;
  Reject<Vulkan::CacheLoadError>([&] { Vulkan::CompileSPV(portable, vk::Device{}, true); });
  Check(vk::calls == before, "unallocated motion buffers reached driver");
  std::vector<u32> first;
  for (unsigned session = 1; session <= 2; ++session) {
    Motion::params_address = 0x100000000ull * session;
    Motion::positions_address = Motion::params_address + 0x10000;
    Vulkan::CompileSPV(portable, vk::Device{}, true);
    Check(portable == original, "module creation changed persistent motion code");
    const std::array<u64, 3> expected{Motion::params_address, Motion::params_address + 16,
                                     Motion::positions_address};
    for (size_t i = 0; i < expected.size(); ++i) {
      const size_t at = Spirv().size() + 4 + i * 5;
      Check((u64(vk::last_code[at + 3]) | u64(vk::last_code[at + 4]) << 32) == expected[i],
            "driver received a stale or unlinked motion address");
    }
    if (session == 1) first = vk::last_code;
    else Check(first != vk::last_code, "driver code did not follow session allocations");
  }
  auto partial = portable;
  partial.resize(partial.size() - 5);
  const auto linked_calls = vk::calls;
  Reject<Vulkan::CacheLoadError>([&] { Vulkan::CompileSPV(partial, vk::Device{}, true); });
  Reject<std::runtime_error>([&] { Vulkan::CompileSPV(partial, vk::Device{}); });
  Check(vk::calls == linked_calls, "partial motion relocations reached driver");
  std::cout << "PASS actual CompileSPV driver boundary: two live buffer allocations, "
               "unchanged persistent code and rejection before driver IO\n";
}
void StorageTest() {
  auto &db = Storage::DataBase::Instance();
  const auto dir = root / "CUSA_CACHE_TEST";
  hold_worker = true;
  db.Open();
  Check(db.IsOpened(), "cache open");
  std::atomic<unsigned> accepted{};
  std::vector<std::thread> producers;
  for (unsigned producer = 0; producer < 4; ++producer)
    producers.emplace_back([&, producer] {
      for (unsigned i = 0; i < 100; ++i)
        if (db.Save(Storage::BlobType::ShaderMeta,
                    std::to_string(producer * 100 + i),
                    std::vector<u8>{u8(i), u8(producer), 23}))
          ++accepted;
    });
  for (auto &p : producers)
    p.join();
  Check(accepted == 400, "submissions lost");
  std::thread closer([&] { db.Close(); });
  const auto deadline =
      std::chrono::steady_clock::now() + std::chrono::seconds(10);
  while (db.IsOpened() && std::chrono::steady_clock::now() < deadline)
    std::this_thread::yield();
  Check(!db.IsOpened(), "close did not reject submissions");
  Check(!db.Save(Storage::BlobType::ShaderMeta, "late", std::vector<u8>{9}),
        "accepted after close");
  hold_worker = false;
  hold_worker.notify_all();
  closer.join();
  db.Open();
  unsigned recovered = 0;
  for (unsigned i = 0; i < 400; ++i) {
    std::vector<u8> data;
    db.Load(Storage::BlobType::ShaderMeta, std::to_string(i), data);
    if (data == std::vector<u8>{u8(i % 100), u8(i / 100), 23})
      ++recovered;
  }
  Check(recovered == 400, "accepted writes canceled during close");
  std::cout << "Accepted cache writes recovered after immediate close: "
            << recovered << "/400\n";
  Write(dir / "legacy.meta", std::array<u8, 3>{9, 8, 7});
  auto bytes = Storage::Blob::Encode(0, std::array<u8, 3>{1, 2, 3});
  bytes.back() ^= 1;
  Write(dir / "broken.meta", bytes);
  Write(dir / "incomplete.meta.tmp", std::array<u8, 3>{1, 2, 3});
  Write(dir / "odd.spv", std::array<u8, 3>{1, 2, 3});
  Write(dir / "huge.meta", std::array<u8, 1>{0});
  std::filesystem::resize_file(dir / "huge.meta",
                               Storage::Blob::PayloadLimit(0) + 33);
  std::vector<u8> data{99};
  db.Load(Storage::BlobType::ShaderMeta, "missing", data);
  Check(data.empty(), "missing leaves stale data");
  db.Load(Storage::BlobType::ShaderMeta, "legacy", data);
  Check(data == std::vector<u8>({9, 8, 7}), "legacy IO");
  db.Load(Storage::BlobType::ShaderMeta, "broken", data);
  Check(data.empty(), "corrupt CRC loaded");
  db.Load(Storage::BlobType::ShaderMeta, "huge", data);
  Check(data.empty(), "oversized loaded");
  std::vector<u32> words;
  db.Load(Storage::BlobType::ShaderBinary, "odd", words);
  Check(words.empty(), "unaligned SPIR-V loaded");
  unsigned count = 0;
  db.ForEachBlob(Storage::BlobType::ShaderMeta, [&](auto &&) { ++count; });
  Check(count == 401, "enumeration includes bad or temp records");
  std::filesystem::create_directory(dir / "blocked.key");
  Write(dir / "blocked.key" / "keep", std::array<u8, 1>{7});
  Check(db.Save(Storage::BlobType::PipelineKey, "blocked",
                std::vector<u8>{1, 2, 3}),
        "enqueue blocked replacement");
  Check(
      db.Save(Storage::BlobType::ShaderMeta, "later", std::vector<u8>{4, 5, 6}),
      "enqueue after failure");
  Check(db.Save(Storage::BlobType::PipelineBinary,"driver",std::vector<u8>{10,20,30}),"pipeline payload enqueue");
  db.Flush();
  db.Load(Storage::BlobType::PipelineBinary,"driver",data);Check(data==std::vector<u8>({10,20,30}),"pipeline payload flush");
  db.Close();
  db.Open();
  db.Load(Storage::BlobType::PipelineBinary,"driver",data);Check(data==std::vector<u8>({10,20,30}),"persistent pipeline payload reopen");
  db.Load(Storage::BlobType::ShaderMeta, "later", data);
  Check(data == std::vector<u8>({4, 5, 6}) &&
            std::filesystem::exists(dir / "blocked.key" / "keep"),
        "failed replacement loses prior target or worker");
  Check(!std::filesystem::exists(dir / "blocked.key.tmp"),
        "failed replacement leaves temp");
  db.Close();
  std::cout << "PASS actual cache IO: missing/corrupt/oversized/temp files and "
               "failed replacement recovery\n";
}
} // namespace
namespace Common::FS {
const std::filesystem::path &GetUserPath(PathType) { return root; }
} // namespace Common::FS
namespace Common {
void SetCurrentThreadName(const char *) { hold_worker.wait(true); }
} // namespace Common
int main(int argc, char **argv) {
  try {
    Check(argc == 2 || argc == 3, "expected isolated cache directory");
    root = std::filesystem::path(argv[1]) /
           std::filesystem::path(u8"cache – 猎人");
    std::filesystem::create_directories(root);
    Serdes();
    Blobs();
    ShaderTest();
    if(argc==3) {
      std::ifstream file(argv[2],std::ios::binary|std::ios::ate);auto length=file.tellg();file.seekg(0);
      Check(length>0 && length%4==0,"legacy SPIR-V length");std::vector<u32> old(size_t(length)/4);file.read((char*)old.data(),length);
      Vulkan::CompileSPV(old,vk::Device{},true);
      Check(vk::last_code!=old,"actual driver received the broken R52 declaration");
      std::cout<<"PASS R52 shader migration before actual CompileSPV driver boundary\n";
    }
    StorageTest();
    std::cout << "PASS shader cache production regressions\n";
    return 0;
  } catch (const std::exception &error) {
    std::cerr << "FAIL: " << error.what() << '\n';
    return 1;
  }
}
