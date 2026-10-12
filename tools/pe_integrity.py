# SPDX-FileCopyrightText: Copyright 2026 TatsunaKyo
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read Windows import/export closure without executing package binaries."""
import struct
from pathlib import Path

class PE:
    """Read AMD64 import/export tables without executing any Windows program."""
    def __init__(self, path):
        self.path = Path(path)
        self.data = self.path.read_bytes()
        assert self.data[:2] == b'MZ', path
        nt = self.u32(0x3c)
        assert self.data[nt:nt + 4] == b'PE\x00\x00', path
        machine, nsects, _, _, _, optlen, _ = struct.unpack_from('<HHIIIHH', self.data, nt + 4)
        assert machine == 0x8664, (path, machine)
        self.opt = nt + 24
        assert self.u16(self.opt) == 0x20b, path
        self.sections = []
        for i in range(nsects):
            off = self.opt + optlen + i * 40
            _, size, rva, rawsize, rawptr = struct.unpack_from('<8sIIII', self.data, off)
            self.sections.append((rva, max(size, rawsize), rawptr, rawsize))
        self.directories = [struct.unpack_from('<II', self.data, self.opt + 112 + i * 8)
                            for i in range(min(16, self.u32(self.opt + 108)))]

    def u16(self, p): return struct.unpack_from('<H', self.data, p)[0]
    def u32(self, p): return struct.unpack_from('<I', self.data, p)[0]
    def u64(self, p): return struct.unpack_from('<Q', self.data, p)[0]
    def offset(self, rva):
        if rva < self.u32(self.opt + 60):
            return rva
        for start, size, rawptr, rawsize in self.sections:
            if start <= rva < start + size:
                assert rva - start < rawsize, (self.path, hex(rva))
                return rawptr + rva - start
        raise ValueError((self.path, hex(rva)))
    def string(self, rva):
        off = self.offset(rva)
        return self.data[off:self.data.index(0, off)].decode('ascii')
    def imports(self):
        imports = []
        for directory, delay in ((1, False), (13, True)):
            rva, size = self.directories[directory]
            if not rva:
                continue
            p = self.offset(rva)
            step = 32 if delay else 20
            while any(self.data[p:p + step]):
                if delay:
                    attrs, name, _, _, table, _, _, _ = struct.unpack_from('<8I', self.data, p)
                    assert attrs & 1, 'Expected RVA-based delay descriptor'
                else:
                    table, _, _, name, first = struct.unpack_from('<5I', self.data, p)
                    table = table or first
                dll = self.string(name).lower()
                symbols = []
                t = self.offset(table)
                while self.u64(t):
                    value = self.u64(t)
                    symbols.append(value & 0xffff if value & (1 << 63) else self.string(value + 2))
                    t += 8
                imports.append((dll, symbols))
                p += step
        return imports
    def exports(self):
        rva, size = self.directories[0]
        if not rva:
            return {}
        p = self.offset(rva)
        base, nfunc, nname, functions, names, ordinals = struct.unpack_from('<6I', self.data, p + 16)
        result = {}
        for i in range(nfunc):
            value = self.u32(self.offset(functions) + 4 * i)
            if value:
                result[base + i] = self.string(value) if rva <= value < rva + size else None
        for i in range(nname):
            name = self.string(self.u32(self.offset(names) + 4 * i))
            ordinal = base + self.u16(self.offset(ordinals) + 2 * i)
            if ordinal in result:
                result[name] = result[ordinal]
        return result
system = {n + '.dll' for n in '''kernel32 ntdll user32 gdi32 gdi32full advapi32 shell32
ole32 oleaut32 comdlg32 comctl32 ws2_32 wsock32 winmm imm32 setupapi version iphlpapi gdiplus
bcrypt bcryptprimitives crypt32 secur32 uxtheme dxgi d3d9 d3d11 d3d12 dwmapi shlwapi
normaliz wldap32 dnsapi mswsock msvcrt ucrtbase winspool opengl32 winhttp powrprof
avrt propsys psapi dbghelp cfgmgr32 wintrust imagehlp oleacc usp10 wtsapi32 wininet
authz netapi32 userenv hid dxva2 amsi winusb mf mfplat mfreadwrite rpcrt4 cryptbase
win32u dwrite winmmbase mfplay msimg32 d3dcompiler_47 dsound ncrypt keyiso'''.split()}
system.add('winspool.drv')
def is_system(name): return name in system or name.startswith(('api-ms-win-', 'ext-ms-win-'))



def verify_directory(root):
    root=Path(root)
    programs=[PE(p) for p in root.rglob('*') if p.suffix.lower() in ('.exe','.dll','.pyd')
              and p != root/'redist/vc_redist.x64.exe']
    dlls={p.path:p for p in programs if p.path.suffix.lower()=='.dll'}
    exports={path:pe.exports() for path,pe in dlls.items()}
    count=0
    def locate(path,name):
        for folder in (path.parent,root/'bin',root/'_internal'):
            if folder.is_dir():
                for candidate in folder.iterdir():
                    if candidate.is_file() and candidate.name.lower()==name: return candidate
        return None
    for pe in programs:
        for dll,symbols in pe.imports():
            if is_system(dll): continue
            resolved=locate(pe.path,dll)
            if resolved not in dlls: raise ValueError(f'{pe.path.name} is missing dependency {dll}')
            for symbol in symbols:
                if symbol not in exports[resolved]: raise ValueError(f'{pe.path.name}: {dll} has no export {symbol}')
                count+=1
    return {'pe_files_checked':len(programs),'runtime_dlls_checked':len(dlls),'imported_symbols_checked':count}
