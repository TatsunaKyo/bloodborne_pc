"""The side bar's entries for the room they have (launcher/bbport_launcher_win.py nav_plan): on a 1366 x 768 laptop
(the window 700 points high) the expert view's last entries lay behind the Expert view switch, because the entries
stopped at 26 points. Now the head's gaps narrow and the entries get flatter, the by-line goes only after that, and
only where even that is not enough does the list scroll. The window itself: test_launcher_window.SideBarLiveTests."""
from paths import ROOT
import sys
import unittest

sys.path.insert(0, str(ROOT / 'launcher'))
sys.path.insert(0, str(ROOT / 'scripts'))
import bbport_launcher_win as L  # noqa: E402

# Measured at 100 %: the head, the search and everything under the list take 284 points; the narrower gaps give the
# list 35 more, the by-line on top of them 60; the EXPERT label with its gaps takes 30. The expert view has 15
# entries, the simple one 10.
FIXED, SAVINGS, GROUP = 284, (35, 60), 30
# What fit_nav gave nav_plan in the real window (Tk scaled as Windows does), with what it is to show: (scaling, window
# height in points, room under the full head, savings, EXPERT label) -> (entry height, head, scrolls)
MEASURED = [((1.000492, 680, 364, (35, 60), 30), (23, 1, False)),  # the smallest window
            ((1.000492, 688, 372, (35, 60), 30), (24, 1, False)),  # 1366 x 768: the window the launcher opens
            ((1.000492, 700, 384, (35, 60), 30), (24, 1, False)),
            ((1.000492, 760, 444, (35, 60), 30), (26, 0, False)),
            ((1.498525, 640, 516, (51, 83), 39), (23, 1, False)),  # 1920 x 1080 at 150 %
            ((1.498525, 680, 576, (51, 83), 39), (26, 1, False)),  # it lost the by-line for nothing before
            ((1.998033, 640, 684, (69, 111), 49), (23, 1, False)),  # 2560 x 1440 at 200 %
            ((1.249692, 535, 292, (43, 72), 33), (22, 2, True))]  # 1366 x 768 at 125 %


def pixels(dpi):
    return lambda size: int(size * dpi)


class NavPlanTests(unittest.TestCase):
    def test_the_laptop_window(self):
        px = pixels(1.0)
        for window, height, head in ((680, 23, 1), (700, 24, 1), (720, 26, 1), (760, 26, 0), (1000, 37, 0)):
            room = window - 32 - FIXED  # the launcher's title bar above the side bar
            with self.subTest(window=window):
                self.assertEqual(L.nav_plan(room, SAVINGS, 15, GROUP, px), (height, head, False))
        # the simple view keeps the full head down to the smallest window
        self.assertEqual(L.nav_plan(680 - 32 - FIXED, SAVINGS, 10, 0, px), (35, 0, False))

    def test_measured_windows(self):
        for (dpi, window, room, savings, group), plan in MEASURED:
            with self.subTest(dpi=dpi, window=window):
                self.assertEqual(L.nav_plan(room, savings, 15, group, pixels(dpi)), plan)

    def test_the_by_line_stays_while_the_narrow_gaps_hold_23_points(self):
        """The by-line went with the gaps for entries under 26 points before: a point more per entry, and most of
        its room left empty under the list (150 % at 680 points)."""
        for dpi in (1.0, 1.25, 1.5, 1.75, 2.0):
            px = pixels(dpi)
            group, savings = px(GROUP), tuple(px(s) for s in SAVINGS)
            for room in range(px(150), px(700)):
                height, head, _scrolls = L.nav_plan(room, savings, 15, group, px)
                fits = group + 15 * (px(23) + px(1)) <= room + savings[0]
                with self.subTest(dpi=dpi, room=room):
                    self.assertEqual(head < 2, fits)
                    if head == 2:  # and without it the entries are no taller than the by-line would allow
                        self.assertLessEqual(height, 23)

    def test_the_entries_always_fit_or_scroll(self):
        for dpi in (1.0, 1.25, 1.5, 1.75, 2.0):
            px = pixels(dpi)
            group, savings = px(GROUP), tuple(px(s) for s in SAVINGS)
            before = (0, 2, True)
            for room in range(px(150), px(700)):
                height, head, scrolls = plan = L.nav_plan(room, savings, 15, group, px)
                need = group + 15 * (px(height) + px(1))
                with self.subTest(dpi=dpi, room=room):
                    if scrolls:
                        self.assertEqual((height, head), (22, 2))
                        self.assertGreater(need, room + savings[1])  # scrolls only where nothing else would do
                    else:
                        self.assertLessEqual(need, room + (0, *savings)[head])
                    # each head only for entries the head before cannot hold
                    self.assertTrue({0: 26 <= height, 1: 23 <= height <= 26, 2: height <= 23}[head])
                    if head:
                        self.assertGreater(group + 15 * (px((26, 23)[head - 1]) + px(1)),
                                           room + (0, *savings)[head - 1])
                    # more room never makes the entries flatter, the head smaller again or the list scroll
                    self.assertGreaterEqual(height, before[0])
                    self.assertLessEqual((head, scrolls), (before[1], before[2]))
                before = plan

    def test_entries_stay_between_22_and_37_points(self):
        px = pixels(1.5)
        savings = tuple(px(s) for s in SAVINGS)
        self.assertEqual(L.nav_plan(px(2000), savings, 15, px(GROUP), px), (37, 0, False))
        self.assertEqual(L.nav_plan(0, savings, 15, px(GROUP), px), (22, 2, True))


if __name__ == '__main__':
    unittest.main()
