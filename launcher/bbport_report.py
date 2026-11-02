# SPDX-License-Identifier: GPL-2.0-or-later
"""The report of a game test (bbport_benchmark): one HTML file next to the logs and screenshots
in the test's folder, readable offline in any browser, with every measurement as a chart (drawn
here as SVG, no library), the stability verdict, the problems the logs name, the picture
comparison of the screenshots, and samples.csv for a spreadsheet. export() zips the folder."""
import csv
import html
import zipfile
from pathlib import Path

COLORS = ['#c2a878', '#c0392b', '#5b8fd9', '#7fb069', '#b07cc6', '#e0a458', '#4fb3bf', '#d96c9b', '#9a9a9a']
BG, CARD, LINE, TEXT, MUTED, GOLD, BLOOD = '#0d0e10', '#16171a', '#2a2b30', '#d8d3c8', '#8c8880', '#c2a878', '#b3202a'
STATUS = {'ok': ('Completed', GOLD), 'crash': ('Crashed', BLOOD), 'freeze': ('Froze', BLOOD),
          'no start': ('Did not start', BLOOD), 'cancelled': ('Cancelled', MUTED), 'error': ('Error', BLOOD),
          'input': ('Stopped: input from the player', BLOOD)}
SETTING_NAMES = {'output_res': 'Output', 'upscaler': 'Upscaler', 'preset': 'Preset', 'object_motion': 'Object motion',
                 'effect_ssao': 'SSAO', 'effect_dynamic_shadows': 'Dynamic shadows', 'model_lod': 'Model detail',
                 'effect_game_aa': 'Game AA', 'effect_ssr': 'Reflections', 'frame_gen': 'Frame generation'}
PRESETS = {'0': 'Native AA', '1': 'Quality', '2': 'Balanced', '3': 'Performance', '4': 'Ultra Performance'}


def esc(text):
    return html.escape(str(text), quote=True)


def show(key, value):
    if key == 'preset':
        return PRESETS.get(str(value), value)
    if isinstance(value, bool):
        return 'on' if value else 'off'
    return value


def label(run, start):
    """A run's name: what it changes against the start settings."""
    if run.get('display'):
        return run['display']
    changed = [f'{SETTING_NAMES.get(k, k)} {show(k, v)}' for k, v in run['settings'].items() if start.get(k) != v]
    base = {'recommended': 'Recommended', 'lowest': 'Lowest settings', 'stability': 'Stability run'}.get(run['name'])
    return base or (', '.join(changed) if changed else run['name'])


# ---- charts -------------------------------------------------------------------------------------------
def nice(top):
    """A round upper bound for an axis."""
    if top <= 0:
        return 1
    for power in range(-2, 7):
        for step in (1, 1.2, 1.6, 2, 2.4, 3.2, 4, 6, 8):  # a quarter of each is a round number
            value = round(step * 10 ** power, 6)
            if value >= top:
                return value
    return top


def line_chart(title, series, unit, height=230, y_max=None, bands=(), note=''):
    """series: [(name, [(x, y)], color)]; x in seconds."""
    width, left, right, top, bottom = 940, 52, 14, 14, 30
    points = [p for _n, pts, _c in series for p in pts if p[1] is not None]
    if not points:
        return ''
    x_max = max(p[0] for p in points) or 1
    y_top = y_max or nice(max(p[1] for p in points) * 1.08)
    sx = lambda x: left + (width - left - right) * x / x_max
    sy = lambda y: top + (height - top - bottom) * (1 - min(y, y_top) / y_top)
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" aria-label="{esc(title)}">']
    for a, b in bands:
        out.append(f'<rect x="{sx(a):.1f}" y="{top}" width="{max(1, sx(b) - sx(a)):.1f}" height="{height - top - bottom}" '
                   f'fill="{GOLD}" opacity="0.06"/>')
    for i in range(5):
        y = y_top * i / 4
        out.append(f'<line x1="{left}" x2="{width - right}" y1="{sy(y):.1f}" y2="{sy(y):.1f}" stroke="{LINE}"/>')
        out.append(f'<text x="{left - 6}" y="{sy(y) + 4:.1f}" text-anchor="end" class="axis">{y:g}</text>')
    step = nice(x_max / 8)
    x = 0
    while x <= x_max + 0.01:
        out.append(f'<text x="{sx(x):.1f}" y="{height - 10}" text-anchor="middle" class="axis">'
                   f'{(f"{x / 60:g} min" if x_max > 300 else f"{x:g} s")}</text>')
        x += step
    for name, pts, color in series:
        pts = [(x, y) for x, y in pts if y is not None]
        if len(pts) == 1:
            out.append(f'<circle cx="{sx(pts[0][0]):.1f}" cy="{sy(pts[0][1]):.1f}" r="3" fill="{color}"/>')
        elif pts:
            path = ' '.join(f'{sx(x):.1f},{sy(y):.1f}' for x, y in pts)
            out.append(f'<polyline points="{path}" fill="none" stroke="{color}" stroke-width="1.8" '
                       f'stroke-linejoin="round"><title>{esc(name)}</title></polyline>')
    out.append('</svg>')
    legend = ''.join(f'<span><i style="background:{c}"></i>{esc(n)}</span>' for n, _p, c in series if _p)
    return (f'<figure><figcaption>{esc(title)} <small>{esc(unit)}</small></figcaption>{"".join(out)}'
            f'<div class="legend">{legend}</div>{f"<p class=note>{esc(note)}</p>" if note else ""}</figure>')


def bar_chart(title, rows, unit):
    """rows: [(name, value, second value or None, color)]: value as a bar, the second as a mark."""
    rows = [r for r in rows if r[1] is not None]
    if not rows:
        return ''
    width, name_w, bar_h, gap = 940, 330, 22, 10
    height = len(rows) * (bar_h + gap) + 10
    top = nice(max(max(r[1], r[2] or 0) for r in rows) * 1.05)
    scale = lambda v: (width - name_w - 70) * v / top
    out = [f'<svg viewBox="0 0 {width} {height}" class="chart">']
    for i, (name, value, second, color) in enumerate(rows):
        y = 5 + i * (bar_h + gap)
        out.append(f'<text x="{name_w - 10}" y="{y + 15}" text-anchor="end" class="name">{esc(name[:52])}</text>')
        out.append(f'<rect x="{name_w}" y="{y}" width="{scale(value):.1f}" height="{bar_h}" rx="3" fill="{color}"/>')
        out.append(f'<text x="{name_w + scale(value) + 6:.1f}" y="{y + 15}" class="value">{value:.1f}</text>')
        if second:
            out.append(f'<rect x="{name_w + scale(second) - 1.5:.1f}" y="{y - 2}" width="3" height="{bar_h + 4}" '
                       f'fill="{TEXT}"><title>1 % low {second:.1f}</title></rect>')
    out.append('</svg>')
    return f'<figure><figcaption>{esc(title)} <small>{esc(unit)}</small></figcaption>{"".join(out)}</figure>'


# ---- pictures -----------------------------------------------------------------------------------------
def detail_regions(path, count=4, grid=(6, 4)):
    """The image's most detailed cells (edges), away from the HUD corners: [(x0, y0, x1, y1)]."""
    from PIL import Image, ImageFilter, ImageStat
    image = Image.open(path).convert('L')
    w, h = image.size
    small = image.resize((w // 4, h // 4)).filter(ImageFilter.FIND_EDGES)
    cw, ch = w // grid[0], h // grid[1]
    scored = []
    for gx in range(grid[0]):
        for gy in range(grid[1]):
            if (gx, gy) in ((0, 0), (1, 0), (0, grid[1] - 1), (grid[0] - 1, 0)):
                continue  # health bars, items, counters
            box = (gx * cw // 4, gy * ch // 4, (gx + 1) * cw // 4, (gy + 1) * ch // 4)
            scored.append((ImageStat.Stat(small.crop(box)).mean[0], gx, gy))
    chosen = []
    for _score, gx, gy in sorted(scored, reverse=True):
        if all(abs(gx - a) > 1 or abs(gy - b) > 1 for a, b in chosen):
            chosen.append((gx, gy))
        if len(chosen) == count:
            break
    return [(gx * cw, gy * ch, (gx + 1) * cw, (gy + 1) * ch) for gx, gy in chosen]


def picture_section(folder, runs, start):
    shots = [(r, name, file) for r in runs for name, file in r.get('captures', {}).items()
             if (folder / file).is_file()]
    if not shots:
        return ''
    names = sorted({name for _r, name, _f in shots})
    parts = ['<section><h2>Pictures</h2><p class="muted">Screenshots at the same moment of every run. Drag the line '
             'to compare two of them; the mouse wheel zooms (pixels stay sharp).</p>']
    for shot_name in names:
        group = [(r, f) for r, n, f in shots if n == shot_name]
        if not group:
            continue
        options = ''.join(f'<option value="{esc(f)}">{esc(label(r, start))}</option>' for r, f in group)
        parts.append(f'''<div class="viewer" data-group="{esc(shot_name)}">
  <div class="pick"><label>Left <select class="a">{options}</select></label>
  <label>Right <select class="b">{options}</select></label></div>
  <div class="stage"><div class="zoom"><img class="ib" src="{esc(group[-1][1])}" alt="">
  <img class="ia" src="{esc(group[0][1])}" alt=""></div><div class="cut"></div></div></div>''')
        try:
            regions = detail_regions(folder / group[0][1])
            from PIL import Image
        except Exception:
            regions = []
        if regions and len(group) > 1:
            parts.append('<div class="crops" style="grid-template-columns: repeat(%d, 1fr)">' % len(group))
            for r, _f in group:
                parts.append(f'<div class="crophead">{esc(label(r, start))}<br><small>{fmt(r.get("fps"))} FPS'
                             f'</small></div>')
            for index, box in enumerate(regions):
                for _run, f in group:
                    out = f'crop-{Path(f).stem}-{index}.png'
                    Image.open(folder / f).convert('RGB').crop(box).save(folder / out)
                    parts.append(f'<img class="crop" src="{esc(out)}" alt="">')
            parts.append('</div>')
    parts.append('</section>')
    return ''.join(parts)


# ---- the report ---------------------------------------------------------------------------------------
def fmt(value, digits=1):
    return '–' if value is None else f'{value:.{digits}f}'


def peak(run, key):
    values = [s[key] for s in run.get('telemetry', []) if s.get(key) is not None]
    return max(values) if values else None


def write(folder, test, runs):
    folder = Path(folder)
    start = test.get('start') or (runs[0]['settings'] if runs else {})
    color = {r['index']: COLORS[i % len(COLORS)] for i, r in enumerate(runs)}
    named = [(label(r, start) + (f' #{r["index"]}' if sum(label(x, start) == label(r, start) for x in runs) > 1
                                 else ''), r) for r in runs]
    kind = test.get('kind', 'performance')
    title = {'performance': 'Performance test', 'compare': 'Settings comparison',
             'stability': 'Stability test'}.get(kind, 'Game test')

    # the verdict
    verdict = []
    if kind == 'stability' and runs:
        r = runs[0]
        text, tone = STATUS.get(r['status'], (r['status'], MUTED))
        minutes = r.get('seconds', 0) / 60
        verdict.append(f'<div class="verdict" style="border-color:{tone}"><b style="color:{tone}">{esc(text)}</b> '
                       f'after {minutes:.1f} min' + (f': {esc(r.get("message"))}' if r.get('message') else '') + '</div>')
        growth = r.get('ram_growth_gb')
        if growth is not None:
            verdict.append(f'<p>Memory of the game: {"+" if growth >= 0 else ""}{growth:.2f} GB from the first to the '
                           f'last quarter of the run' + (' — <b>it keeps growing</b> (a leak would end in a crash on '
                                                        'longer sessions).' if growth > 0.5 else '.') + '</p>')
    elif kind == 'performance':
        choice = next((r for r in runs if r['index'] == test.get('choice')), None)
        if choice:
            verdict.append(f'<div class="verdict"><b>Best for {test.get("goal") and round(test["goal"])} FPS:</b> '
                           f'{esc(label(choice, start))} — {fmt(choice.get("fps"))} FPS</div>')
        if test.get('floor'):
            verdict.append(f'<p class="muted">With the lowest settings this PC reached {fmt(test["floor"])} FPS: above '
                           'that the processor or the game itself sets the limit, not the graphics settings.</p>')

    # the table
    rows = []
    for name, r in named:
        text, tone = STATUS.get(r['status'], (r['status'], MUTED))
        rows.append(f'<tr><td><i class="dot" style="background:{color[r["index"]]}"></i>{esc(name)}</td>'
                    f'<td style="color:{tone}">{esc(text)}</td><td>{fmt(r.get("fps"))}</td><td>{fmt(r.get("low1"))}</td>'
                    f'<td>{fmt(r.get("p99_ms"), 2)}</td><td>{fmt(r.get("worst_ms"))}</td><td>{r.get("stutters", "–")}</td>'
                    f'<td>{r.get("compiles", "–")}</td><td>{fmt(peak(r, "ram_gb"), 2)}</td><td>{fmt(peak(r, "vram_gb"), 2)}</td>'
                    f'<td class="small">{esc(r.get("upscaler", ""))}</td></tr>')
    table = ('<table><thead><tr><th>Run</th><th>Result</th><th>FPS</th><th>1 % low</th><th>p99 ms</th>'
             '<th>Worst frame ms</th><th>Stutters</th><th>Shader compiles</th><th>RAM GB</th><th>VRAM GB</th>'
             '<th>Upscaler</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table>')

    # each measured part of a scenario with several (standing, camera turn, walk)
    parts = ''.join(f'<tr><td><i class="dot" style="background:{color[r["index"]]}"></i>{esc(name)}</td>'
                    f'<td>{esc(s["name"])}</td><td>{fmt(s.get("fps"))}</td><td>{fmt(s.get("low1"))}</td>'
                    f'<td>{fmt(s.get("worst_ms"))}</td></tr>'
                    for name, r in named for s in r.get('sections', []))
    if parts:
        table += ('<h2>Each part of the route</h2><table><thead><tr><th>Run</th><th>Part</th><th>FPS</th>'
                  '<th>1 % low</th><th>Worst frame ms</th></tr></thead><tbody>' + parts + '</tbody></table>')

    # the port's own view (scenarios for bug reports): what the texture cache and VRAM went through
    details = []
    for name, r in named:
        p = r.get('port')
        if not p:
            continue
        vram = f'<a href="{esc(p["vram_file"])}">allocator statistics</a>' if p.get('vram_file') else '–'
        details.append(f'<tr><td><i class="dot" style="background:{color[r["index"]]}"></i>{esc(name)}</td>'
                       f'<td>{p["evicted"]} / {p["written_back"]} / {p["dropped"]}</td>'
                       f'<td>{p["port_vram_mib"] if p.get("port_vram_mib") is not None else "–"}</td>'
                       f'<td>{p["vram_full"]}</td><td>{p["stale_cache"]}</td><td>{p["failed_pipelines"]}</td>'
                       f'<td>{p["device_lost"]}</td><td>{vram}</td></tr>')
    if details:
        setup = next((r['port']['setup'] for r in runs if r.get('port', {}).get('setup')), [])
        table += ('<h2>Port details</h2><table><thead><tr><th>Run</th><th>Textures evicted / written back / dropped'
                  '</th><th>VRAM peak MiB (renderer)</th><th>"Video memory full"</th><th>Shader cache from another '
                  'build</th><th>Failed pipelines</th><th>Device lost</th><th>VRAM by purpose</th></tr></thead><tbody>'
                  + ''.join(details) + '</tbody></table>'
                  + ('<details><summary>Setup (from the log)</summary><div class="log">'
                     + ''.join(f'<div>{esc(line)}</div>' for line in setup) + '</div></details>' if setup else ''))

    # the charts
    pts = lambda rows, key: [(x['t'], x.get(key)) for x in rows]
    charts = []
    if len(runs) > 1:
        charts.append(bar_chart('Average FPS and 1 % low (the mark) per run',
                                [(n, r.get('fps'), r.get('low1'), color[r['index']]) for n, r in named], 'FPS'))
    bands = [(a, b) for _n, a, b in runs[0].get('windows', [])] if len(runs) == 1 else []
    charts.append(line_chart('Frame rate over time', [(n, pts(r['frames'], 'fps'), color[r['index']]) for n, r in named],
                             'FPS, every 5 s', bands=bands, note='The shaded parts are the measured seconds.' if bands else ''))
    charts.append(line_chart('Frame time, 99th percentile', [(n, pts(r['pacing'], 'p99_ms'), color[r['index']])
                                                            for n, r in named], 'ms (lower is smoother)', bands=bands))
    charts.append(line_chart('Slowest frame', [(n, pts(r['frames'], 'worst_ms'), color[r['index']]) for n, r in named],
                             'ms per 5 s', bands=bands))
    charts.append(line_chart('Stutters', [(n, pts(r['pacing'], 'stutters'), color[r['index']]) for n, r in named],
                             'frames over 1.5× the median, per 5 s', bands=bands))
    charts.append(line_chart('Shader compiles', [(n, pts(r['frames'], 'compiles'), color[r['index']]) for n, r in named],
                             'per 5 s (the cache fills; later runs need fewer)', bands=bands))
    charts.append(line_chart('Game memory (RAM)', [(n, pts(r['telemetry'], 'ram_gb'), color[r['index']])
                                                    for n, r in named], 'GB, private bytes', bands=bands))
    charts.append(line_chart('Graphics memory (VRAM)', [(n, pts(r['telemetry'], 'vram_gb'), color[r['index']])
                                                         for n, r in named], 'GB, this game only', bands=bands))
    charts.append(line_chart('Processor load', [(n, pts(r['telemetry'], 'cpu'), color[r['index']]) for n, r in named],
                             '% of all cores', y_max=100, bands=bands))
    charts.append(line_chart('Graphics card load', [(n, pts(r['telemetry'], 'gpu'), color[r['index']])
                                                     for n, r in named], '% (3D engine)', y_max=100, bands=bands))
    charts.append(line_chart('Memory free for programs', [(n, pts(r['telemetry'], 'free_gb'), color[r['index']])
                                                           for n, r in named], 'GB (RAM and page file)', bands=bands))
    charts.append(line_chart('Draws per frame', [(n, pts(r['frames'], 'draws'), color[r['index']]) for n, r in named],
                             'how much the scene has (the same route draws the same)', bands=bands))

    # problems
    problems = []
    try:
        from bbport_help import TOPICS
    except ImportError:
        TOPICS = {}
    for name, r in named:
        found = [TOPICS[t][0] for t in r.get('hints', []) if t in TOPICS]
        events = r.get('events', [])
        if not found and not events and r['status'] == 'ok':
            continue
        lines = ''.join(f'<li>{esc(f)}</li>' for f in found)
        log = ''.join(f'<div><span class="t">{e["t"]:.0f} s</span> {esc(e["text"])}</div>' for e in events[:60])
        problems.append(f'<details{" open" if r["status"] != "ok" else ""}><summary>{esc(name)}: '
                        f'{len(events)} error lines{", known causes: " + str(len(found)) if found else ""}</summary>'
                        f'{f"<ul>{lines}</ul>" if lines else ""}<div class="log">{log or "–"}</div>'
                        f'<p class="muted">Full log: <a href="{esc(r["log"])}">{esc(r["log"])}</a></p></details>')

    info = ''.join(f'<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>' for k, v in test.items()
                   if k not in ('start', 'choice', 'kind') and v not in (None, '', {}))
    settings = ''.join(f'<tr><td>{esc(SETTING_NAMES.get(k, k))}</td><td>{esc(show(k, v))}</td></tr>'
                       for k, v in start.items())
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(title)} – Bloodborne PC port</title>
<style>
:root {{ color-scheme: dark; }}
* {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}  /* printed or saved as PDF: the colours stay */
figure, details, .viewer, tr {{ break-inside: avoid; }}
body {{ background:{BG}; color:{TEXT}; font:14px/1.5 "Segoe UI", Inter, sans-serif; margin:0; }}
main {{ max-width:1000px; margin:0 auto; padding:28px 18px 60px; }}
h1 {{ font:600 26px Georgia, serif; color:{GOLD}; letter-spacing:.04em; margin:0 0 4px; }}
h2 {{ font:600 18px Georgia, serif; color:{GOLD}; margin:34px 0 10px; border-bottom:1px solid {LINE}; padding-bottom:6px; }}
.muted, small, .note {{ color:{MUTED}; }}
.verdict {{ background:{CARD}; border-left:3px solid {GOLD}; padding:12px 16px; border-radius:6px; margin:14px 0; font-size:15px; }}
table {{ width:100%; border-collapse:collapse; background:{CARD}; border-radius:6px; overflow:hidden; font-size:13px; }}
th, td {{ padding:7px 9px; text-align:left; border-bottom:1px solid {LINE}; }}
th {{ color:{MUTED}; font-weight:600; }} td.small {{ font-size:11px; color:{MUTED}; }}
.dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:7px; }}
figure {{ background:{CARD}; border-radius:8px; padding:12px 14px 8px; margin:14px 0; }}
figcaption {{ font-weight:600; margin-bottom:6px; }}
.chart {{ width:100%; height:auto; display:block; }}
.chart .axis {{ fill:{MUTED}; font-size:11px; }} .chart .name {{ fill:{TEXT}; font-size:12px; }}
.chart .value {{ fill:{TEXT}; font-size:12px; font-weight:600; }}
.legend span {{ margin-right:14px; font-size:12px; color:{MUTED}; white-space:nowrap; }}
.legend i {{ display:inline-block; width:12px; height:3px; margin:0 6px 3px 0; vertical-align:middle; }}
details {{ background:{CARD}; border-radius:6px; padding:10px 14px; margin:8px 0; }}
summary {{ cursor:pointer; font-weight:600; }}
.log {{ font:12px/1.45 Consolas, monospace; max-height:280px; overflow:auto; margin-top:8px; white-space:pre-wrap; }}
.log .t {{ color:{GOLD}; margin-right:6px; }}
a {{ color:{GOLD}; }}
.viewer {{ background:{CARD}; border-radius:8px; padding:12px; margin:14px 0; }}
.pick {{ display:flex; gap:18px; flex-wrap:wrap; margin-bottom:10px; }}
select {{ background:{BG}; color:{TEXT}; border:1px solid {LINE}; border-radius:4px; padding:4px 6px; max-width:100%; }}
.stage {{ position:relative; overflow:hidden; cursor:ew-resize; border-radius:4px; }}
.zoom {{ position:relative; transform-origin:0 0; }}
.zoom img {{ display:block; width:100%; image-rendering:pixelated; }}
.zoom .ia {{ position:absolute; left:0; top:0; clip-path:inset(0 50% 0 0); }}
.cut {{ position:absolute; top:0; bottom:0; left:50%; width:2px; background:{GOLD}; pointer-events:none; }}
.crops {{ display:grid; gap:6px; margin-top:12px; }}
.crops img {{ width:100%; image-rendering:pixelated; border-radius:3px; }}
.crophead {{ font-size:12px; font-weight:600; }}
</style></head><body><main>
<h1>{esc(title)}</h1>
<p class="muted">{esc(test.get("scenario", ""))} · {esc(test.get("date", ""))} · Bloodborne PC port</p>
{"".join(verdict)}
<h2>Results</h2>{table}
<h2>Charts</h2>{"".join(c for c in charts if c)}
{picture_section(folder, runs, start)}
<h2>Problems found</h2>{"".join(problems) or '<p class="muted">No error lines and no known causes in the logs.</p>'}
<h2>This PC and the test</h2><table>{info}</table>
<h2>Start settings</h2><table>{settings}</table>
<p class="muted">Files in this folder: results.json (every sample), samples.csv (for a spreadsheet), run-N.log
(the game's log of each run), the screenshots.</p>
</main>
<script>
document.querySelectorAll('.viewer').forEach(v => {{
  const stage = v.querySelector('.stage'), zoom = v.querySelector('.zoom'), a = v.querySelector('.ia'),
        b = v.querySelector('.ib'), cut = v.querySelector('.cut');
  let split = 0.5, scale = 1, ox = 0, oy = 0;
  const draw = () => {{
    zoom.style.transform = `translate(${{ox}}px, ${{oy}}px) scale(${{scale}})`;
    const x = split * stage.clientWidth, inner = (x - ox) / scale / zoom.clientWidth;
    a.style.clipPath = `inset(0 ${{Math.max(0, 100 - inner * 100)}}% 0 0)`;
    cut.style.left = x + 'px';
  }};
  stage.addEventListener('mousemove', e => {{ if (e.buttons || !e.shiftKey) {{
    split = Math.min(1, Math.max(0, (e.clientX - stage.getBoundingClientRect().left) / stage.clientWidth)); draw(); }} }});
  stage.addEventListener('wheel', e => {{
    e.preventDefault();
    const r = stage.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    const next = Math.min(8, Math.max(1, scale * (e.deltaY < 0 ? 1.25 : 0.8)));
    ox = mx - (mx - ox) * next / scale; oy = my - (my - oy) * next / scale; scale = next;
    if (scale === 1) {{ ox = 0; oy = 0; }}
    ox = Math.min(0, Math.max(stage.clientWidth * (1 - scale), ox));
    oy = Math.min(0, Math.max(stage.clientHeight * (1 - scale), oy)); draw();
  }}, {{ passive: false }});
  v.querySelector('.a').addEventListener('change', e => {{ a.src = e.target.value; }});
  v.querySelector('.b').addEventListener('change', e => {{ b.src = e.target.value; }});
  const sb = v.querySelector('.b'); sb.selectedIndex = sb.options.length - 1;
  draw();
}});
</script></body></html>'''
    (folder / 'report.html').write_text(page, encoding='utf-8')
    write_csv(folder, named)
    return folder / 'report.html'


def write_csv(folder, named):
    with open(folder / 'samples.csv', 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['run', 'name', 'seconds', 'fps', 'worst_ms', 'p99_ms', 'median_ms', 'stutters', 'compiles', 'draws',
                    'ram_gb', 'vram_gb', 'cpu_percent', 'gpu_percent', 'free_gb', 'not_responding'])
        for name, r in named:
            rows = {}
            for f in r['frames']:
                rows.setdefault(round(f['t']), {}).update(f)
            for p in r['pacing']:
                rows.setdefault(round(p['t']), {}).update(p)
            for s in r['telemetry']:
                rows.setdefault(round(s['t']), {}).update(s)
            for t in sorted(rows):
                x = rows[t]
                w.writerow([r['index'], name, t] + [('' if x.get(k) is None else round(x[k], 3) if isinstance(x[k], float)
                                                     else x[k]) for k in ('fps', 'worst_ms', 'p99_ms', 'median_ms',
                                                                          'stutters', 'compiles', 'draws', 'ram_gb',
                                                                          'vram_gb', 'cpu', 'gpu', 'free_gb', 'hung')])


def export(folder, target=None):
    """The test's folder as a zip (on the desktop unless `target` is given); its path."""
    import os
    folder = Path(folder)
    if not target:
        desktop = Path(os.environ.get('USERPROFILE', '.')) / 'Desktop'
        target = (desktop if desktop.is_dir() else folder.parent) / f'bbport-test-{folder.name}.zip'
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(folder.iterdir()):
            if path.is_file():
                z.write(path, path.name)
    return Path(target)
