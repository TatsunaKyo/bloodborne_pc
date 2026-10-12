/* SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
 * SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef _WIN32
#define _POSIX_C_SOURCE 200809L
#endif
#include "save_access.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <sys/stat.h>
#ifdef _WIN32
#include <windows.h>
static HANDLE lease = INVALID_HANDLE_VALUE;
#else
#include <fcntl.h>
#include <sys/file.h>
#include <unistd.h>
static int lease = -1;
#endif

void bb_save_access_release(void) {
#ifdef _WIN32
    if (lease != INVALID_HANDLE_VALUE) { CloseHandle(lease); lease = INVALID_HANDLE_VALUE; }
#else
    if (lease >= 0) { close(lease); lease = -1; }
#endif
}

int bb_save_access_acquire(const char *user, char *message, size_t capacity) {
    char path[1024];
    int count = snprintf(path, sizeof(path), "%s/.crowned-workshop-save.lock", user);
    if (count < 0 || (size_t)count >= sizeof(path)) {
        snprintf(message, capacity, "The saves folder path is too long."); return -1;
    }
#ifdef _WIN32
    if (lease != INVALID_HANDLE_VALUE) {
#else
    if (lease >= 0) {
#endif
        snprintf(message, capacity, "The runtime already holds a saves lease."); return -1;
    }
#ifdef _WIN32
    WCHAR wide[1024];
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide, 1024)) {
        snprintf(message, capacity, "The saves folder path is not valid UTF-8."); return -1;
    }
    DWORD attrs = GetFileAttributesW(wide);
    if (attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_REPARSE_POINT)) {
        snprintf(message, capacity, "The saves lock must not be a link or junction."); return -1;
    }
    lease = CreateFileW(wide, GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        NULL, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, NULL);
    OVERLAPPED position = {0};
    if (lease == INVALID_HANDLE_VALUE ||
        !LockFileEx(lease, LOCKFILE_EXCLUSIVE_LOCK | LOCKFILE_FAIL_IMMEDIATELY, 0, 1, 0, &position)) {
        bb_save_access_release();
        snprintf(message, capacity, "The saves folder is in use or cannot be locked. Close the other game/save operation."); return -1;
    }
#else
    lease = open(path, O_RDWR | O_CREAT | O_NOFOLLOW, 0600);
    struct stat info;
    if (lease < 0 || fstat(lease, &info) || !S_ISREG(info.st_mode) || flock(lease, LOCK_EX | LOCK_NB)) {
        bb_save_access_release();
        snprintf(message, capacity, "The saves folder is in use or cannot be locked. Close the other game/save operation."); return -1;
    }
    /* Linux restarts close this descriptor before exec, just like the Windows
     * restart waits for the previous process to terminate. */
    fcntl(lease, F_SETFD, FD_CLOEXEC);
#endif
    count = snprintf(path, sizeof(path), "%s/.crowned-workshop-restore.json", user);
    int pending = count < 0 || (size_t)count >= sizeof(path);
#ifdef _WIN32
    if (!pending) {
        pending = !MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide, 1024);
        if (!pending) {
            DWORD journal_attrs = GetFileAttributesW(wide);
            pending = journal_attrs != INVALID_FILE_ATTRIBUTES ||
                      (GetLastError() != ERROR_FILE_NOT_FOUND && GetLastError() != ERROR_PATH_NOT_FOUND);
        }
    }
#else
    if (!pending) {
        struct stat journal;
        pending = !lstat(path, &journal) || errno != ENOENT;
    }
#endif
    if (pending) {
        bb_save_access_release();
        snprintf(message, capacity, "An interrupted save restore needs recovery. Open Save Manager in the launcher before playing."); return -1;
    }
    atexit(bb_save_access_release);
    return 0;
}
