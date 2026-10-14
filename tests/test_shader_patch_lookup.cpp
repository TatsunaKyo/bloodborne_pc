// SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
// SPDX-License-Identifier: GPL-2.0-or-later
// Run the production lookup with real filesystem operations and a recorded IO boundary.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <optional>
#include <string>
#include <string_view>
#include <vector>
using u32 = std::uint32_t;
using u64 = std::uint64_t;
namespace Shader { enum class HwStage { Vertex }; }
static std::filesystem::path root;
static unsigned path_lookups{}, formats{}, file_opens{};
struct Settings {
    bool patch{}, collect{};
    bool IsPatchShaders() const { return patch; }
    bool IsShaderCollect() const { return collect; }
} EmulatorSettings;
namespace Common::FS {
enum class PathType { ShaderDir };
enum class FileAccessMode { Read };
auto GetUserPath(PathType) { ++path_lookups; return root; }
struct IOFile {
    std::filesystem::path path;
    IOFile(std::filesystem::path p, FileAccessMode) : path(std::move(p)) { ++file_opens; }
    auto GetSize() const { return std::filesystem::file_size(path); }
    void Read(std::vector<u32>& out) const {
        std::ifstream file(path, std::ios::binary);
        file.read(reinterpret_cast<char*>(out.data()), out.size() * sizeof(u32));
        assert(file.good());
    }
};
}
namespace fmt {
auto format(const char*, const std::string& name, std::string_view ext) {
    ++formats; return name + "." + std::string(ext);
}
}
namespace Vulkan {
struct PipelineCache {
    std::optional<std::vector<u32>> GetShaderPatch(u64, Shader::HwStage, std::size_t, std::string_view);
    std::string GetShaderName(Shader::HwStage, u64, std::size_t) { return "test"; }
};
#include "production_patch_lookup.inc"
}
int main(int argc, char** argv) {
    assert(argc == 2); root = std::filesystem::path(argv[1]);
    std::filesystem::create_directories(root);
    Vulkan::PipelineCache cache;
    auto lookup = [&] { return cache.GetShaderPatch(17, Shader::HwStage::Vertex, 0, "spv"); };
    assert(!lookup());
#if CONTROL
    assert(path_lookups == 1 && formats == 1 && std::filesystem::is_directory(root / "patch"));
    std::puts("CONTROL: R35 probes/creates the shader patch directory even while both features are disabled.");
    return 7;
#else
    for (int i = 0; i < 100; ++i) assert(!lookup());
    assert(path_lookups == 0 && formats == 0 && file_opens == 0);
    assert(!std::filesystem::exists(root / "patch"));
    // Disabled lookup must also succeed when its path cannot be a directory.
    const auto directory = root;
    root /= "ordinary-file"; { std::ofstream file(root); file << "not a directory"; }
    assert(!lookup() && path_lookups == 0); root = directory;
    EmulatorSettings.patch = true;
    assert(!lookup() && std::filesystem::is_directory(root / "patch"));
    const std::vector<u32> expected{0x07230203, 0x00010600, 7, 8};
    { std::ofstream file(root / "patch/test.spv", std::ios::binary);
      file.write(reinterpret_cast<const char*>(expected.data()), expected.size() * sizeof(u32)); }
    assert(lookup() == expected && file_opens == 1);
    EmulatorSettings.patch = false; EmulatorSettings.collect = true;
    assert(lookup() == expected && file_opens == 2);
    EmulatorSettings.collect = false;
    const auto before = path_lookups;
    assert(!lookup() && path_lookups == before && file_opens == 2);
    std::puts("PASS: disabled production patch lookup performs no path/format/file work; enabled patches and debug collection still load identical SPIR-V words.");
#endif
}
