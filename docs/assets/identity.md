# The Crowned Workshop

I wanted the fork to feel like my own workshop, with a quiet hunter at a workbench, warm lantern light and a pale-red moon outside. The banner carries the name and my signature. I kept the technical features in the README so the artwork has room to breathe.

The crowned TK emblem combines my initials, an open crown, a Gothic workshop arch and a workbench. Its paths are editable, and the simple silhouette survives small icon sizes. It is an original project mark, separate from Bloodborne's official logo and Hunter's Mark.

| Asset | Use |
|---|---|
| `crowned-workshop-header.png` | Main README banner, 1800 × 700. The standing hunter and full workshop are the moon concept. |
| `tatsunakyo-header.svg` | Editable lettering and emblem over the moon painting. Keep its sibling background PNG beside it. |
| `crowned-workshop-lantern.png` / `.svg` | A closer lantern concept, also 1800 × 700, with the same identity. |
| `crowned-workshop-art-moon.png` / `crowned-workshop-art-lantern.png` | The original background illustrations, without type or an emblem. |
| `crowned-workshop-emblem.svg` | Editable vector mark, with named crown, arch, initial and workbench paths. |
| `crowned-workshop-emblem-64.png`, `-256.png`, `-512.png` | Transparent PNG marks. |
| `crowned-workshop-icon.svg`, `crowned-workshop-icon-64.png`, `-256.png` | The emblem on a dark tile, for readable window/executable icons on both light and dark desktops. |
| `crowned-workshop.ico` | Windows icon with 16/24/32/48/64/128/256-pixel sizes. |

The PNG banner is used in the README because it displays consistently on GitHub, including mobile. The SVG lettering remains editable; it uses Georgia with DejaVu Serif as a fallback. To export after an edit, install CairoSVG and Pillow and run `python tools/export_brand_assets.py` from the repository. The two paintings stay unchanged when the SVG is exported.

Art direction and project identity: TatsunaKyo. The workshop paintings were created for this brief using image generation; typography, emblem and exports are editable project assets. See [the artwork prompts](artwork-prompts.md) for the brief. The original game and upstream port keep their own credits.

## README feature diagrams

I used the same dark panels, warm brass lettering and crowned TK mark for the feature overviews. Each image sits beside the explanation it introduces; the diagrams keep the broad idea readable before the tables and details. All eleven have editable SVG sources and PNG exports in `docs/assets/features/`. Run `python tools/export_feature_infographics.py` to regenerate them with CairoSVG and Pillow. The export also creates a mobile-width proof sheet for checking the type.
