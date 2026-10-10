# Streamline declarations

These MIT-licensed NVIDIA headers come from the official Streamline 2.14.1 SDK: https://github.com/NVIDIAGameWorks/Streamline/releases/tag/v2.14.1. Only API declarations and the signature-verification helper are included here; production DLLs are shipped separately in the Windows package with their own licenses.

Two compatibility edits are needed for this project's Clang/MinGW build: Windows SDK include names in `sl_security.h` use lowercase filenames, and the C++23 `std::to_underlying` function is imported with a using-declaration in `sl_pcl.h`. These do not change the API layout. All original NVIDIA copyright notices remain in the headers.
