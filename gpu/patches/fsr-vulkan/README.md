# Local changes to gpu/third_party/fsr-vulkan

The submodule points at upstream FireBurn/FSR-Vulkan (`c64f093`). `build.sh` applies the
patches here to its working tree when they are not applied yet:

- `0001-...`: `BB_FSR4_PROFILE` (GPU time per FSR 4 pass) and `BB_FSR4_STATS` (driver
  statistics of each pass) in the FSR 4 v07 provider.
- `0002-...`: `#include <mutex>` in the FFX Vulkan backend; libc++ (the Windows MSYS2 CLANG64
  build) does not include it transitively.
- `0003-...`: the same explicit include for the older FFX 1.1.4 Vulkan backend, which is still built alongside the current providers.
- `0004-...`: FSR 3.1 frame generation tells the bridge which frame its jobs belong to and
  retires that frame with the imported views. Without it every constant buffer and descriptor
  set the bridge made (one allocation each, per generated frame) was kept until the context
  was destroyed: video memory grew by about 60 MiB a second until the device was lost.
- `0005-...`: the FFX Vulkan backend never picks a protected memory type unless it asked for one.
  On RADV PHOENIX (Ryzen Z1 Extreme: ROG Ally, Legion Go) it picked one for FSR 3.1's
  device-local resources, and the scene was white or full of colored noise (#85). Also sent to
  FireBurn/FSR-Vulkan#1.
