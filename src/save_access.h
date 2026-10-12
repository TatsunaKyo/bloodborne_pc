/* SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
 * SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include <stddef.h>

/* Hold the same byte-range/file lease as scripts/save_access.py. This must be
 * acquired before the sound flag correction or any guest save write. */
int bb_save_access_acquire(const char *user, char *message, size_t capacity);
void bb_save_access_release(void);
