/* SPDX-License-Identifier: GPL-2.0-or-later
 * SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo */
#ifndef BB_RUNTIME_ASSET_IO_H
#define BB_RUNTIME_ASSET_IO_H
#include <stdint.h>
#include <stddef.h>
#ifdef _WIN32
/* A separate file object for concurrent, offset-based reads of read-only assets.
 * The caller keeps it alive until all pending reads have returned. */
void *runtime_asset_reader_open(int fd);
void runtime_asset_reader_close(void *reader);
int64_t runtime_asset_read_at(void *reader, void *buffer, size_t size, int64_t offset);
#endif
#endif
