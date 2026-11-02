"""The controller test's reader (launcher/bbport_pad.py), on a stand-in for SDL3: which controllers
are connected, their kind, buttons and axes; gone ones are closed."""
from paths import ROOT
import ctypes
import sys
import unittest

sys.path.insert(0, str(ROOT / 'launcher'))
import bbport_pad  # noqa: E402


class FakeSDL:
    """SDL3's gamepad calls as bbport_pad uses them."""

    def __init__(self):
        self.pads = {7: ('DualSense Wireless Controller', 6, {0, 9}, {0: 32767, 4: 32767})}
        self.closed = []
        self.ids = None

    def SDL_UpdateGamepads(self):
        pass

    def SDL_GetGamepads(self, count):
        ids = list(self.pads)
        count._obj.value = len(ids)
        self.ids = (ctypes.c_uint32 * max(1, len(ids)))(*ids)
        return self.ids

    def SDL_free(self, pointer):
        pass

    def SDL_OpenGamepad(self, ident):
        return ident + 1000

    def SDL_CloseGamepad(self, handle):
        self.closed.append(handle)

    def SDL_GetGamepadName(self, handle):
        return self.pads[handle - 1000][0].encode()

    def SDL_GetGamepadType(self, handle):
        return self.pads[handle - 1000][1]

    def SDL_GetGamepadButton(self, handle, button):
        return button in self.pads[handle - 1000][2]

    def SDL_GetGamepadAxis(self, handle, axis):
        return self.pads[handle - 1000][3].get(axis, 0)


class PadTests(unittest.TestCase):
    def reader(self):
        pads = bbport_pad.Pads.__new__(bbport_pad.Pads)
        pads.sdl, pads.open = FakeSDL(), {}
        return pads

    def test_what_the_game_sees(self):
        pads = self.reader()
        pad, = pads.poll()
        self.assertEqual((pad.name, pad.kind), ('DualSense Wireless Controller', 'playstation'))
        self.assertEqual([b for b, on in pad.buttons.items() if on], ['south', 'left_shoulder'])
        self.assertEqual((pad.axes['left_x'], pad.axes['left_trigger'], pad.axes['right_y']), (1.0, 1.0, 0.0))

    def test_xbox_buttons_for_every_other_controller(self):
        pads = self.reader()
        pads.sdl.pads = {3: ('Controller (Xbox One For Windows)', 3, set(), {})}
        self.assertEqual(pads.poll()[0].kind, 'xbox')

    def test_a_controller_that_is_gone_is_closed(self):
        pads = self.reader()
        pads.poll()
        pads.sdl.pads = {}
        self.assertEqual(pads.poll(), [])
        self.assertEqual(pads.sdl.closed, [1007])

    def test_the_ports_own_sdl(self):
        self.assertIsNone(bbport_pad.sdl_path(ROOT / 'nowhere'))



class PictureTests(unittest.TestCase):
    """The controller's picture (launcher/bbport_pad_art.py): every layout at the size asked for, and a
    pressed button, a pulled trigger and a pushed stick change it where they are."""

    def setUp(self):
        try:
            import bbport_pad_art
        except ImportError:  # no Pillow
            self.skipTest('Pillow is missing')
        self.art = bbport_pad_art

    def test_every_layout_at_its_size(self):
        for kind in ('playstation', 'xbox', 'switch', 'unknown'):
            for width in (480, 720):
                with self.subTest(kind=kind, width=width):
                    self.assertEqual(self.art.render(kind, width=width).size, (width, round(width * 380 / 600)))

    def test_what_is_used_lights_up(self):
        from PIL import ImageChops
        rest = self.art.render('playstation', width=480).convert('RGB')  # the colours (getbbox of RGBA: alpha only)
        for buttons, axes in (({'south': True}, {}), ({}, {'right_trigger': 1.0}), ({}, {'left_x': 1.0})):
            with self.subTest(buttons=buttons, axes=axes):
                used = self.art.render('playstation', buttons, axes, width=480).convert('RGB')
                self.assertIsNotNone(ImageChops.difference(rest, used).getbbox())
        self.assertIsNone(ImageChops.difference(rest, self.art.render('playstation', width=480).convert('RGB')).getbbox())


if __name__ == '__main__':
    unittest.main()
