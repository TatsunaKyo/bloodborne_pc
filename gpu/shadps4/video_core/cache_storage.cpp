// SPDX-FileCopyrightText: Copyright 2025-2026 shadPS4 Emulator Project
// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later

#include "video_core/cache_storage.h"
#include "common/cache_blob.h"
#include "common/elf_info.h"
#include "common/polyfill_thread.h"
#include "common/thread.h"
#include "core/emulator_settings.h"
#include <array>
#include <condition_variable>
#include <cstring>
#include <fstream>
#include <future>
#include <miniz.h>
#include <mutex>
#include <queue>
#include <span>

namespace {
std::mutex request_mutex{};
std::condition_variable_any request_cv{};
std::queue<std::packaged_task<void()>> req_queue{};
bool accepting_requests{};
mz_zip_archive zip_ar{};
bool ar_is_read_only{true};
} // namespace

namespace Storage {
void ProcessIO(const std::stop_token &stoken) {
  Common::SetCurrentThreadName("shadPS4:PipelineCacheIO");
  for (;;) {
    std::packaged_task<void()> request{};
    {
      std::unique_lock lock{request_mutex};
      Common::CondvarWait(request_cv, lock, stoken,
                          [] { return !req_queue.empty(); });
      if (req_queue.empty()) {
        if (stoken.stop_requested())
          break;
        continue;
      }
      request = std::move(req_queue.front());
      req_queue.pop();
    }
    // Close rejects new submissions, then drains everything already accepted.
    auto result = request.get_future();
    request();
    try {
      result.get();
    } catch (const std::exception &error) {
      LOG_WARNING(Render, "Cache write failed: {}", error.what());
    }
  }
}

constexpr std::string GetBlobFileExtension(BlobType type) {
  switch (type) {
  case BlobType::ShaderMeta:
    return "meta";
  case BlobType::ShaderBinary:
    return "spv";
  case BlobType::PipelineKey:
    return "key";
  case BlobType::PipelineBinary:
    return "vkp";
  case BlobType::ShaderProfile:
    return "bin";
  default:
    UNREACHABLE();
  }
}

void DataBase::Open() {
  if (opened)
    return;
  const auto &game_info = Common::ElfInfo::Instance();
  using namespace Common::FS;
  std::error_code error;
  std::filesystem::create_directories(GetUserPath(PathType::CacheDir), error);
  if (error) {
    LOG_WARNING(Render, "Cannot open shader cache: {}", error.message());
    return;
  }
  if (EmulatorSettings.IsPipelineCacheArchived()) {
    mz_zip_zero_struct(&zip_ar);
    ar_is_read_only = true;
    cache_path =
        GetUserPath(PathType::CacheDir) /
        std::filesystem::path{game_info.GameSerial()}.replace_extension(".zip");
    if (!mz_zip_reader_init_file(&zip_ar, cache_path.string().c_str(),
                                 MZ_ZIP_FLAG_READ_ALLOW_WRITING) ||
        !mz_zip_validate_archive(&zip_ar, 0)) {
      mz_zip_reader_end(&zip_ar);
      if (!mz_zip_writer_init_file(&zip_ar, cache_path.string().c_str(), 0)) {
        LOG_WARNING(Render, "Cannot initialize cache archive");
        return;
      }
      ar_is_read_only = false;
    }
  } else {
    cache_path = GetUserPath(PathType::CacheDir) / game_info.GameSerial();
    std::filesystem::create_directories(cache_path, error);
    if (error) {
      LOG_WARNING(Render, "Cannot open shader cache: {}", error.message());
      return;
    }
  }
  {
    std::scoped_lock lock{request_mutex};
    accepting_requests = true;
  }
  io_worker = std::jthread{ProcessIO};
  opened = true;
}

void DataBase::Flush() {
  auto done = std::make_shared<std::promise<void>>();
  auto ready = done->get_future();
  {
    std::scoped_lock lock{request_mutex};
    if (!accepting_requests) return;
    req_queue.emplace([done] { done->set_value(); });
  }
  request_cv.notify_one();
  ready.get();
}

void DataBase::Close() {
  if (!opened.exchange(false))
    return;
  {
    std::scoped_lock lock{request_mutex};
    accepting_requests = false;
  }
  io_worker.request_stop();
  request_cv.notify_all();
  io_worker.join();
  if (EmulatorSettings.IsPipelineCacheArchived()) {
    if (!ar_is_read_only) {
      mz_zip_writer_finalize_archive(&zip_ar);
      mz_zip_writer_end(&zip_ar);
    } else
      mz_zip_reader_end(&zip_ar);
  }
  LOG_INFO(Render, "Cache dumped");
}

template <typename T>
bool WriteVector(BlobType type, std::filesystem::path &&path_,
                 std::vector<T> &&data) {
  if (data.size() > Blob::PayloadLimit(u32(type)) / sizeof(T))
    return false;
  auto request = std::packaged_task<void()>{[type, path = std::move(path_),
                                             data = std::move(data)]() mutable {
    path.replace_extension(GetBlobFileExtension(type));
    const auto payload = std::span(reinterpret_cast<const u8 *>(data.data()),
                                   data.size() * sizeof(T));
    const auto encoded = Blob::Encode(u32(type), payload);
    if (EmulatorSettings.IsPipelineCacheArchived()) {
      if (ar_is_read_only ||
          !mz_zip_writer_add_mem(&zip_ar, path.string().c_str(), encoded.data(),
                                 encoded.size(), MZ_BEST_COMPRESSION))
        LOG_WARNING(Render, "Failed to add shader cache record {}",
                    path.string());
      return;
    }
    auto temp = path;
    temp += ".tmp";
    std::error_code error;
    {
      std::ofstream file(temp, std::ios::binary | std::ios::trunc);
      file.write(reinterpret_cast<const char *>(encoded.data()),
                 encoded.size());
      file.flush();
      const bool written = bool(file);
      file.close();
      if (!written || file.fail()) {
        LOG_WARNING(Render, "Cannot write cache record {}", path.string());
        std::filesystem::remove(temp, error);
        return;
      }
    }
    std::filesystem::rename(temp, path, error);
    if (error) {
      LOG_WARNING(Render, "Cannot replace cache record {}: {}", path.string(),
                  error.message());
      std::filesystem::remove(temp, error);
    }
  }};
  {
    std::scoped_lock lock{request_mutex};
    if (!accepting_requests)
      return false;
    req_queue.emplace(std::move(request));
  }
  request_cv.notify_one();
  return true;
}

template <typename T>
void LoadVector(BlobType type, std::filesystem::path &path,
                std::vector<T> &data) {
  data.clear();
  path.replace_extension(GetBlobFileExtension(type));
  const size_t limit = Blob::PayloadLimit(u32(type)) + Blob::HeaderSize;
  std::vector<u8> bytes;
  if (EmulatorSettings.IsPipelineCacheArchived()) {
    const int index =
        mz_zip_reader_locate_file(&zip_ar, path.string().c_str(), nullptr, 0);
    mz_zip_archive_file_stat stat{};
    if (index < 0 || !mz_zip_reader_file_stat(&zip_ar, index, &stat) ||
        !stat.m_uncomp_size || stat.m_uncomp_size > limit)
      return;
    bytes.resize(size_t(stat.m_uncomp_size));
    if (!mz_zip_reader_extract_to_mem(&zip_ar, index, bytes.data(),
                                      bytes.size(), 0))
      return;
  } else {
    std::error_code error;
    if (!std::filesystem::is_regular_file(
            std::filesystem::symlink_status(path, error)))
      return;
    const auto size = std::filesystem::file_size(path, error);
    if (error || !size || size > limit)
      return;
    std::ifstream file(path, std::ios::binary);
    if (!file)
      return;
    bytes.resize(size_t(size));
    if (!file.read(reinterpret_cast<char *>(bytes.data()), bytes.size()))
      return;
  }
  std::span<const u8> payload;
  if (!Blob::Decode(u32(type), bytes, payload) || payload.size() % sizeof(T)) {
    LOG_WARNING(Render, "Ignoring damaged cache record {}", path.string());
    return;
  }
  data.resize(payload.size() / sizeof(T));
  if (!payload.empty())
    std::memcpy(data.data(), payload.data(), payload.size());
}

bool DataBase::Save(BlobType type, const std::string &name,
                    std::vector<u8> &&data) {
  if (!opened)
    return false;
  auto path = EmulatorSettings.IsPipelineCacheArchived()
                  ? std::filesystem::path{name}
                  : cache_path / name;
  return WriteVector(type, std::move(path), std::move(data));
}
bool DataBase::Save(BlobType type, const std::string &name,
                    std::vector<u32> &&data) {
  if (!opened)
    return false;
  auto path = EmulatorSettings.IsPipelineCacheArchived()
                  ? std::filesystem::path{name}
                  : cache_path / name;
  return WriteVector(type, std::move(path), std::move(data));
}
void DataBase::Load(BlobType type, const std::string &name,
                    std::vector<u8> &data) {
  data.clear();
  if (!opened)
    return;
  auto path = EmulatorSettings.IsPipelineCacheArchived()
                  ? std::filesystem::path{name}
                  : cache_path / name;
  LoadVector(type, path, data);
}
void DataBase::Load(BlobType type, const std::string &name,
                    std::vector<u32> &data) {
  data.clear();
  if (!opened)
    return;
  auto path = EmulatorSettings.IsPipelineCacheArchived()
                  ? std::filesystem::path{name}
                  : cache_path / name;
  LoadVector(type, path, data);
}

void DataBase::ForEachBlob(
    BlobType type, const std::function<void(std::vector<u8> &&)> &func) {
  if (!opened)
    return;
  const auto extension = "." + GetBlobFileExtension(type);
  if (EmulatorSettings.IsPipelineCacheArchived()) {
    const auto count = mz_zip_reader_get_num_files(&zip_ar);
    for (mz_uint index = 0; index < count; ++index) {
      std::array<char, MZ_ZIP_MAX_ARCHIVE_FILENAME_SIZE> name{};
      mz_zip_reader_get_filename(&zip_ar, index, name.data(), name.size());
      auto path = std::filesystem::path{name.data()};
      if (path.extension() != extension)
        continue;
      std::vector<u8> data;
      LoadVector(type, path, data);
      if (!data.empty())
        func(std::move(data));
    }
  } else {
    std::error_code error;
    auto it = std::filesystem::directory_iterator(cache_path, error);
    const auto end = std::filesystem::directory_iterator{};
    while (!error && it != end) {
      auto path = it->path();
      it.increment(error);
      if (path.extension() != extension)
        continue;
      std::vector<u8> data;
      LoadVector(type, path, data);
      if (!data.empty())
        func(std::move(data));
    }
  }
}

void DataBase::Clear() {
  if (!opened)
    return;
  if (EmulatorSettings.IsPipelineCacheArchived()) {
    if (ar_is_read_only)
      mz_zip_reader_end(&zip_ar);
    else
      mz_zip_writer_end(&zip_ar);
    mz_zip_zero_struct(&zip_ar);
    ar_is_read_only = false;
    mz_zip_writer_init_file(&zip_ar, cache_path.string().c_str(), 0);
    return;
  }
  std::error_code error;
  u64 removed = 0;
  auto it = std::filesystem::directory_iterator(cache_path, error);
  const auto end = std::filesystem::directory_iterator{};
  while (!error && it != end) {
    const auto path = it->path();
    it.increment(error);
    std::error_code file_error;
    if (std::filesystem::is_regular_file(
            std::filesystem::symlink_status(path, file_error)) &&
        std::filesystem::remove(path, file_error))
      ++removed;
  }
  LOG_WARNING(Render,
              "Pipeline cache cleared ({} files): it is rebuilt for this build",
              removed);
}
void DataBase::FinishPreload() {
  if (opened && EmulatorSettings.IsPipelineCacheArchived() && ar_is_read_only) {
    if (mz_zip_writer_init_from_reader(&zip_ar, cache_path.string().c_str()))
      ar_is_read_only = false;
    else
      LOG_WARNING(Render, "Cannot enable cache archive writes");
  }
}
} // namespace Storage
