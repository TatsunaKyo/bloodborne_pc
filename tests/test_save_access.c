/* SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
 * SPDX-License-Identifier: GPL-2.0-or-later */
#include "save_access.h"
#include <stdio.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#else
#include <unistd.h>
#endif

static int check(const char *root, int hold) {
    char message[256];
    if (bb_save_access_acquire(root, message, sizeof(message))) {
        fprintf(stderr, "%s\n", message); return 3;
    }
    puts("ACQUIRED"); fflush(stdout);
    if (hold) {
#ifdef _WIN32
        Sleep(120000);
#else
        sleep(120);
#endif
    }
    bb_save_access_release();
    return 0;
}

#ifdef _WIN32
int wmain(int argc, WCHAR **argv) {
    char root[2048];
    if (argc < 2 || !WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, argv[1], -1, root, sizeof(root), NULL, NULL)) return 2;
    return check(root, argc > 2 && !wcscmp(argv[2], L"hold"));
}
#else
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    return check(argv[1], argc > 2 && !strcmp(argv[2], "hold"));
}
#endif
