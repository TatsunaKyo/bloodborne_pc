#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Can the game's renderer start on this PC? Asks the Vulkan loader (vulkan-1.dll) for exactly what the
renderer refuses to start without (gpu/shadps4/video_core/renderer_vulkan: vk_platform.cpp and
vk_instance.cpp), on the graphics card it would use: no list of card names, the driver's own answer.

The launcher runs it in a process of its own (a broken driver ends that one, not the launcher). It
prints one JSON object:

    {"ok": true/false, "problem": null | "loader" | "loader_version" | "devices" | "device",
     "loader": "1.3.280", "device": {"name", "api", "type", "missing": [...]}, "devices": [...],
     "unseen": ["NVIDIA GeForce RTX 5070 Ti"], "held_back": [{"name", "missing": [...]}]}

"unseen": graphics cards Windows has (DXGI) and Vulkan does not list, while the game would not run on a
working discrete card: a GeForce whose Vulkan driver does not answer leaves the game on the processor's
graphics (a player's RTX 5070 Ti, 30 October 2026). "held_back": discrete cards Vulkan lists but whose driver
lacks something, while the game runs on the processor's graphics (only then present).

tests/test_vulkan_check.py keeps API, REQUIRED_EXTENSIONS and REQUIRED_FEATURES equal to the renderer's."""
import ctypes
import json
import os
import sys

API = (1 << 22) | (3 << 12)  # VK_API_VERSION_1_3: the loader and the card need at least this
REQUIRED_EXTENSIONS = ('VK_KHR_swapchain', 'VK_KHR_push_descriptor', 'VK_EXT_vertex_attribute_divisor',
                       'VK_EXT_robustness2')
REQUIRED_FEATURES = ('robustBufferAccess2', 'robustImageAccess2', 'nullDescriptor')  # of VK_EXT_robustness2
DISCRETE, CPU = 2, 4  # VkPhysicalDeviceType
TYPES = {0: 'other', 1: 'integrated', 2: 'discrete', 3: 'virtual', 4: 'cpu'}
VENDORS = (0x10DE, 0x1002, 0x8086)  # NVIDIA, AMD, Intel: not virtual displays, remote desktops or DisplayLink


def version_text(version):
    return f'{(version >> 22) & 0x7f}.{(version >> 12) & 0x3ff}.{version & 0xfff}'


def ranked(devices):
    """The order vk_instance.cpp picks a card in when BB_GPU_ID is not set: Vulkan 1.3 first, then a
    discrete card, then anything but a software renderer, then the most video memory."""
    return sorted(range(len(devices)), key=lambda i: (devices[i]['api'] < API, devices[i]['type'] != DISCRETE,
                                                      devices[i]['type'] == CPU, -devices[i]['memory']))


def missing(device):
    """What the renderer needs and this card's driver does not offer, in the renderer's order."""
    lacking = [] if device['api'] >= API else [f'Vulkan 1.3 ({version_text(device["api"])})']
    lacking += [name for name in REQUIRED_EXTENSIONS if name not in device['extensions']]
    if 'VK_EXT_robustness2' in device['extensions']:
        lacking += [name for name in REQUIRED_FEATURES if not device['features'].get(name)]
    return lacking


def unseen(devices, adapters):
    """The names of Windows' cards (adapters: DXGI's) that are not among Vulkan's devices: the same vendor
    and device id, or the same name."""
    seen = {(d.get('vendor'), d.get('device_id')) for d in devices}
    names = {d['name'].strip().casefold() for d in devices}
    return [a['name'] for a in adapters if a['vendor'] in VENDORS and (a['vendor'], a['device_id']) not in seen
            and a['name'].strip().casefold() not in names]


def evaluate(loader, devices, gpu_id=None, adapters=()):
    """The verdict from what the loader said (pure: tests give it made-up cards). loader: the loader's
    version, or None without a usable vulkan-1.dll; gpu_id: BB_GPU_ID as the game reads it; adapters:
    the cards Windows has."""
    result = {'ok': False, 'problem': None, 'loader': version_text(loader) if loader else None, 'device': None,
              'devices': [{'name': d['name'], 'api': version_text(d['api']), 'type': TYPES.get(d['type'], '?'),
                           'missing': missing(d)} for d in devices], 'unseen': []}
    if loader is None:
        result['problem'] = 'loader'
    elif loader < API:
        result['problem'] = 'loader_version'
    elif not devices:
        result['problem'] = 'devices'
    else:
        index = ranked(devices)[0]
        if gpu_id not in (None, ''):
            try:
                index = int(gpu_id)
            except ValueError:
                index = -1
            if not 0 <= index < len(devices):
                result['problem'] = 'devices'  # the game stops: no card with that number
                return result
        result['device'] = result['devices'][index]
        result['problem'] = 'device' if result['device']['missing'] else None
    result['ok'] = result['problem'] is None
    # A card Vulkan does not see matters when the game would not run on a working discrete one.
    if result['problem'] in ('devices', 'device') or result['ok'] and result['device']['type'] != 'discrete':
        result['unseen'] = unseen(devices, adapters)
    # A discrete card its driver holds back (Vulkan 1.2, an extension missing) while the game runs on the processor's
    # graphics: a GTX 1060 with an old driver left the game on a Radeon Vega (R29).
    if result['ok'] and result['device']['type'] != 'discrete':
        result['held_back'] = [{'name': d['name'], 'missing': d['missing']} for d in result['devices']
                               if d['type'] == 'discrete' and d['missing']]
    return result


# ---- the Vulkan loader, through ctypes ----------------------------------------------------------
c = ctypes


class ApplicationInfo(c.Structure):
    _fields_ = [('sType', c.c_uint32), ('pNext', c.c_void_p), ('pApplicationName', c.c_char_p),
                ('applicationVersion', c.c_uint32), ('pEngineName', c.c_char_p), ('engineVersion', c.c_uint32),
                ('apiVersion', c.c_uint32)]


class InstanceCreateInfo(c.Structure):
    _fields_ = [('sType', c.c_uint32), ('pNext', c.c_void_p), ('flags', c.c_uint32),
                ('pApplicationInfo', c.POINTER(ApplicationInfo)), ('enabledLayerCount', c.c_uint32),
                ('ppEnabledLayerNames', c.c_void_p), ('enabledExtensionCount', c.c_uint32),
                ('ppEnabledExtensionNames', c.c_void_p)]


class ExtensionProperties(c.Structure):
    _fields_ = [('extensionName', c.c_char * 256), ('specVersion', c.c_uint32)]


class Robustness2Features(c.Structure):
    _fields_ = [('sType', c.c_uint32), ('pNext', c.c_void_p)] + [(name, c.c_uint32) for name in REQUIRED_FEATURES]


class Features2(c.Structure):
    _fields_ = [('sType', c.c_uint32), ('pNext', c.c_void_p), ('features', c.c_uint32 * 55)]


class MemoryHeap(c.Structure):
    _fields_ = [('size', c.c_uint64), ('flags', c.c_uint32)]


class MemoryProperties(c.Structure):
    _fields_ = [('memoryTypeCount', c.c_uint32), ('memoryTypes', c.c_uint32 * 64), ('memoryHeapCount', c.c_uint32),
                ('memoryHeaps', MemoryHeap * 16)]


FEATURES_2, ROBUSTNESS_2_FEATURES = 1000059000, 1000286000  # VkStructureType
DEVICE_LOCAL = 1


def query():
    """(loader version or None, [card]) as vulkan-1.dll answers."""
    try:
        vk = c.WinDLL('vulkan-1') if os.name == 'nt' else c.CDLL('libvulkan.so.1')
    except OSError:
        return None, []
    version = c.c_uint32(1 << 22)  # a 1.0 loader has no vkEnumerateInstanceVersion
    if hasattr(vk, 'vkEnumerateInstanceVersion') and vk.vkEnumerateInstanceVersion(c.byref(version)) != 0:
        return None, []
    if version.value < API:
        return version.value, []
    app = ApplicationInfo(0, None, b'bbport start check', 1, b'bbport', 1, API)
    create = InstanceCreateInfo(1, None, 0, c.pointer(app), 0, None, 0, None)
    instance = c.c_void_p()
    if vk.vkCreateInstance(c.byref(create), None, c.byref(instance)) != 0:
        return version.value, []
    vk.vkDestroyInstance.argtypes = [c.c_void_p, c.c_void_p]
    try:
        vk.vkEnumeratePhysicalDevices.argtypes = [c.c_void_p, c.POINTER(c.c_uint32), c.c_void_p]
        count = c.c_uint32()
        if vk.vkEnumeratePhysicalDevices(instance, c.byref(count), None) != 0 or not count.value:
            return version.value, []
        handles = (c.c_void_p * count.value)()
        if vk.vkEnumeratePhysicalDevices(instance, c.byref(count), handles) not in (0, 5):  # 5: VK_INCOMPLETE
            return version.value, []
        for name in ('vkGetPhysicalDeviceProperties', 'vkGetPhysicalDeviceMemoryProperties',
                     'vkGetPhysicalDeviceFeatures2'):
            getattr(vk, name).argtypes = [c.c_void_p, c.c_void_p]
            getattr(vk, name).restype = None
        vk.vkEnumerateDeviceExtensionProperties.argtypes = [c.c_void_p, c.c_char_p, c.POINTER(c.c_uint32),
                                                            c.c_void_p]
        devices = []
        for handle in handles[:count.value]:
            properties = (c.c_ubyte * 2048)()  # VkPhysicalDeviceProperties: 824 bytes; only its start is read
            vk.vkGetPhysicalDeviceProperties(handle, properties)
            api, device_type = c.c_uint32.from_buffer(properties, 0).value, c.c_uint32.from_buffer(properties, 16).value
            vendor, device_id = c.c_uint32.from_buffer(properties, 8).value, c.c_uint32.from_buffer(properties, 12).value
            name = bytes(properties[20:276]).split(b'\0', 1)[0].decode('utf-8', 'replace')
            memory = MemoryProperties()
            vk.vkGetPhysicalDeviceMemoryProperties(handle, c.byref(memory))
            local = max((memory.memoryHeaps[i].size for i in range(min(memory.memoryHeapCount, 16))
                         if memory.memoryHeaps[i].flags & DEVICE_LOCAL), default=0)
            number = c.c_uint32()
            extensions = set()
            if vk.vkEnumerateDeviceExtensionProperties(handle, None, c.byref(number), None) == 0 and number.value:
                listed = (ExtensionProperties * number.value)()
                if vk.vkEnumerateDeviceExtensionProperties(handle, None, c.byref(number), listed) in (0, 5):
                    extensions = {e.extensionName.decode('ascii', 'replace') for e in listed[:number.value]}
            features = {}
            if 'VK_EXT_robustness2' in extensions:
                robustness = Robustness2Features(ROBUSTNESS_2_FEATURES, None)
                chain = Features2(FEATURES_2, c.cast(c.pointer(robustness), c.c_void_p))
                vk.vkGetPhysicalDeviceFeatures2(handle, c.byref(chain))
                features = {name: bool(getattr(robustness, name)) for name in REQUIRED_FEATURES}
            devices.append({'name': name, 'api': api, 'type': device_type, 'memory': local,
                            'extensions': extensions, 'features': features, 'vendor': vendor,
                            'device_id': device_id})
        return version.value, devices
    finally:
        vk.vkDestroyInstance(instance, None)


# ---- Windows' own list of graphics cards (DXGI), through ctypes -----------------------------------
class AdapterDesc1(c.Structure):
    _fields_ = [('Description', c.c_wchar * 128), ('VendorId', c.c_uint32), ('DeviceId', c.c_uint32),
                ('SubSysId', c.c_uint32), ('Revision', c.c_uint32), ('DedicatedVideoMemory', c.c_size_t),
                ('DedicatedSystemMemory', c.c_size_t), ('SharedSystemMemory', c.c_size_t),
                ('AdapterLuid', c.c_uint32 * 2), ('Flags', c.c_uint32)]


class Guid(c.Structure):
    _fields_ = [('Data1', c.c_uint32), ('Data2', c.c_uint16), ('Data3', c.c_uint16), ('Data4', c.c_ubyte * 8)]


IID_FACTORY_1 = Guid(0x770aae78, 0xf26f, 0x4dba, (c.c_ubyte * 8)(0xa8, 0x29, 0x25, 0x3c, 0x83, 0xd1, 0xb3, 0x87))
SOFTWARE_ADAPTER = 2  # DXGI_ADAPTER_FLAG_SOFTWARE: Microsoft Basic Render Driver


def com_method(pointer, index, *argtypes):
    """Method number index of a COM object's table (IUnknown's three first)."""
    table = c.cast(pointer, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(c.c_long, c.c_void_p, *argtypes)(table[index])


def windows_adapters():
    """[{'name', 'vendor', 'device_id', 'memory'}] of the cards Windows drives (without its software renderer),
    whether Vulkan sees them or not; [] off Windows or when DXGI does not answer."""
    if os.name != 'nt':
        return []
    try:
        dxgi = c.WinDLL('dxgi')
        factory = c.c_void_p()
        if dxgi.CreateDXGIFactory1(c.byref(IID_FACTORY_1), c.byref(factory)) != 0:
            return []
    except (OSError, AttributeError):
        return []
    adapters = []
    try:
        enum_adapters = com_method(factory, 12, c.c_uint32, c.POINTER(c.c_void_p))  # IDXGIFactory1::EnumAdapters1
        for number in range(16):
            adapter = c.c_void_p()
            if enum_adapters(factory, number, c.byref(adapter)) != 0:  # DXGI_ERROR_NOT_FOUND after the last
                break
            try:
                desc = AdapterDesc1()
                if com_method(adapter, 10, c.POINTER(AdapterDesc1))(adapter, c.byref(desc)) == 0 \
                        and not desc.Flags & SOFTWARE_ADAPTER:  # IDXGIAdapter1::GetDesc1
                    adapters.append({'name': desc.Description, 'vendor': desc.VendorId, 'device_id': desc.DeviceId,
                                     'memory': desc.DedicatedVideoMemory})
            finally:
                com_method(adapter, 2)(adapter)  # Release
    finally:
        com_method(factory, 2)(factory)
    return adapters


def main():
    adapters = windows_adapters()
    loader, devices = query()
    result = evaluate(loader, devices, os.environ.get('BB_GPU_ID'), adapters)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
