/* SPDX-License-Identifier: GPL-2.0-or-later
 * SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo */
#include "runtime_asset_io.h"
#ifdef _WIN32
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <io.h>
#include <errno.h>
#include <limits.h>
int compat_errno_from_win32(unsigned long error);

void *runtime_asset_reader_open(int fd) {
    HANDLE original = (HANDLE)_get_osfhandle(fd);
    if (original == INVALID_HANDLE_VALUE) return NULL;
    /* ReOpenFile keeps the exact file selected by the CRT (including mod links),
     * but creates an independent file object. DuplicateHandle would share its
     * synchronous cursor/serialization. Leave Windows' normal cache policy alone. */
    HANDLE reader = ReOpenFile(original, GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, FILE_FLAG_OVERLAPPED);
    return reader == INVALID_HANDLE_VALUE ? NULL : reader;
}

void runtime_asset_reader_close(void *reader) { if (reader) CloseHandle(reader); }

int64_t runtime_asset_read_at(void *reader, void *buffer, size_t size, int64_t offset) {
    if (!reader) { errno = EBADF; return -1; }
    if (offset < 0 || size > INT64_MAX || (uint64_t)offset > INT64_MAX - size) {
        errno = EINVAL; return -1;
    }
    if (!size) return 0;
    /* Each outstanding request has its own event, even when several guest IO
     * workers read the same archive. Nothing moves the sequential CRT cursor. */
    HANDLE event = CreateEventW(NULL, TRUE, FALSE, NULL);
    if (!event) { errno = compat_errno_from_win32(GetLastError()); return -1; }
    size_t done = 0;
    int error = 0;
    while (done < size) {
        DWORD chunk = size - done > 0x40000000u ? 0x40000000u : (DWORD)(size - done);
        DWORD count = 0;
        uint64_t position = (uint64_t)offset + done;
        OVERLAPPED at = {0};
        at.Offset = (DWORD)position; at.OffsetHigh = (DWORD)(position >> 32); at.hEvent = event;
        ResetEvent(event);
        BOOL ok = ReadFile(reader, (char *)buffer + done, chunk, &count, &at);
        DWORD result = ok ? ERROR_SUCCESS : GetLastError();
        if (!ok && result == ERROR_IO_PENDING) {
            ok = GetOverlappedResult(reader, &at, &count, TRUE);
            result = ok ? ERROR_SUCCESS : GetLastError();
        }
        if (!ok) {
            if (result != ERROR_HANDLE_EOF) error = compat_errno_from_win32(result);
            break;
        }
        done += count;
        if (count < chunk) break;
    }
    CloseHandle(event);
    if (error && !done) { errno = error; return -1; }
    return (int64_t)done;
}
#endif
