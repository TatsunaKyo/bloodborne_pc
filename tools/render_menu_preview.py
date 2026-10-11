"""Export the actual ImGui menu draw data captured by test_overlay_controls.py."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image

parser = argparse.ArgumentParser()
parser.add_argument('capture', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
data = json.loads(args.capture.read_text())
width, height = map(int, data['display'])
aw, ah = data['atlas']
atlas = np.frombuffer(args.capture.with_suffix('.atlas').read_bytes(), np.uint8).reshape(ah, aw, 4).astype(np.float32) / 255
# A neutral backing keeps this a UI layout preview, with no invented gameplay scene.
canvas = np.empty((height, width, 4), np.float32)
canvas[:] = [12 / 255, 15 / 255, 18 / 255, 1]
for draw in data['lists']:
    vertices = np.asarray(draw['vertices'], dtype=np.float64)
    indices = np.asarray(draw['indices'], dtype=np.int64)
    colors = vertices[:, 4].astype(np.uint32)
    rgba = np.stack([(colors >> n) & 255 for n in (0, 8, 16, 24)], axis=1).astype(np.float32) / 255
    for cmd in draw['commands']:
        left, top, right, bottom = cmd['clip']
        for offset in range(cmd['offset'], cmd['offset'] + cmd['count'], 3):
            ids = indices[offset:offset + 3] + cmd['base']
            tri = vertices[ids, :4]
            x0 = max(0, int(np.floor(max(left, tri[:, 0].min()))))
            y0 = max(0, int(np.floor(max(top, tri[:, 1].min()))))
            x1 = min(width, int(np.ceil(min(right, tri[:, 0].max()))))
            y1 = min(height, int(np.ceil(min(bottom, tri[:, 1].max()))))
            if x1 <= x0 or y1 <= y0:
                continue
            a, b, c = tri
            determinant = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(determinant) < 1e-9:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float64)
            xx += .5
            yy += .5
            wa = ((b[1] - c[1]) * (xx - c[0]) + (c[0] - b[0]) * (yy - c[1])) / determinant
            wb = ((c[1] - a[1]) * (xx - c[0]) + (a[0] - c[0]) * (yy - c[1])) / determinant
            wc = 1 - wa - wb
            # Apply the top/left edge rule so adjoining triangles blend each pixel once.
            def top_left(p, q):
                if determinant < 0:
                    p, q = q, p
                dx, dy = q[:2] - p[:2]
                return dy < 0 or (abs(dy) < 1e-9 and dx > 0)
            mask = np.ones(wa.shape, dtype=bool)
            for barycentric, edge in zip((wa, wb, wc), ((b, c), (c, a), (a, b))):
                mask &= (barycentric > 1e-9) | ((abs(barycentric) <= 1e-9) & top_left(*edge))
            if not mask.any():
                continue
            weights = np.stack([wa[mask], wb[mask], wc[mask]], axis=1)
            uv = weights @ tri[:, 2:4]
            # Match the atlas's linear sampler; a half texel places sample centers correctly.
            tx = np.clip(uv[:, 0] * aw - .5, 0, aw - 1)
            ty = np.clip(uv[:, 1] * ah - .5, 0, ah - 1)
            ix, iy = tx.astype(int), ty.astype(int)
            fx, fy = (tx - ix)[:, None], (ty - iy)[:, None]
            jx, jy = np.minimum(ix + 1, aw - 1), np.minimum(iy + 1, ah - 1)
            texture = (atlas[iy, ix] * (1 - fx) + atlas[iy, jx] * fx) * (1 - fy)
            texture += (atlas[jy, ix] * (1 - fx) + atlas[jy, jx] * fx) * fy
            sample = texture * (weights @ rgba[ids])
            target = canvas[y0:y1, x0:x1]
            old = target[mask]
            alpha = sample[:, 3:4]
            target[mask, :3] = sample[:, :3] * alpha + old[:, :3] * (1 - alpha)
            target[mask, 3] = sample[:, 3] + old[:, 3] * (1 - sample[:, 3])
x, y, w, h = data['window']
crop = canvas[max(0, int(y) - 8):min(height, int(y + h) + 8),
              max(0, int(x) - 8):min(width, int(x + w) + 8)]
args.output.parent.mkdir(parents=True, exist_ok=True)
Image.fromarray(np.rint(np.clip(crop, 0, 1) * 255).astype(np.uint8)).save(args.output)
print(args.output)
