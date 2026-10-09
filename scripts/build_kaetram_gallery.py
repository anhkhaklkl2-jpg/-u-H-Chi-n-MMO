# -*- coding: utf-8 -*-
"""Build docs/_kaetram_world_preview.html — zoomable gallery of Kaetram map previews."""
import base64
import glob
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREV = os.path.join(ROOT, "docs", "_kaetram_previews")
OUT = os.path.join(ROOT, "docs", "_kaetram_world_preview.html")

TITLES = {
    "world_full": "world_full.json — TOÀN BỘ WORLD (1152x1008 tile, 16px)",
    "world_r13_c8": "r13_c8 — rừng máu (dark biome)",
    "world_r10_c5": "r10_c5 — tuyết / băng hồ",
    "world_r5_c10": "r5_c10 — đảo + hồ nước",
    "world_r0_c0": "r0_c0 — rỗng trong source",
    "world_r9_c6": "r9_c6",
    "world_r6_c4": "r6_c4",
    "world_r12_c3": "r12_c3",
}

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Kaetram preview v11</title>
<style>
  body {{ background:#0f141a; color:#ddd; font-family:ui-monospace,monospace; margin:0; padding:16px; }}
  h1 {{ font-size:18px; }} h2 {{ font-size:14px; margin:22px 0 6px; color:#9fd; }}
  .viewer {{ position:relative; overflow:hidden; border:1px solid #3a4a58; background:#111;
             height:70vh; cursor:grab; }}
  .viewer.dragging {{ cursor:grabbing; }}
  .viewer img {{ position:absolute; top:0; left:0; transform-origin:0 0; image-rendering:pixelated; }}
  .bar {{ display:flex; gap:8px; align-items:center; margin:6px 0; font-size:12px; flex-wrap:wrap; }}
  button {{ background:#1d2a36; color:#cfe; border:1px solid #3a4a58; padding:4px 10px; cursor:pointer;
            border-radius:4px; font-family:inherit; }}
  button:hover {{ background:#26384a; }}
  .hint {{ color:#789; }}
</style></head>
<body>
<h1>Kaetram preview v11 — stack đầy đủ + decor đúng vị trí (fix world_full index decode)</h1>
<p class="hint">Cuộn chuột để zoom quanh con trỏ · kéo để pan · nút 1x/2x/4x · Fit = vừa khung.
Ảnh render từ chính JSON output (layer Decor đã bake sprite cây/đá/bụi, frame đầu của spritesheet).</p>
{blocks}
<script>
document.querySelectorAll('.viewer').forEach(function (v) {{
  var img = v.querySelector('img'), scale = 1, pressed = false, sx = 0, sy = 0, ox = 0, oy = 0;
  function apply() {{ img.style.transform = 'translate(' + ox + 'px,' + oy + 'px) scale(' + scale + ')'; }}
  function fit() {{
    var k = Math.min(v.clientWidth / img.naturalWidth, v.clientHeight / img.naturalHeight);
    scale = k; ox = 0; oy = 0; apply();
  }}
  v.querySelectorAll('button').forEach(function (b) {{
    b.addEventListener('click', function () {{
      var t = b.dataset.z;
      if (t === 'fit') return fit();
      scale = parseFloat(t); ox = 0; oy = 0; apply();
    }});
  }});
  v.addEventListener('wheel', function (e) {{
    e.preventDefault();
    var r = v.getBoundingClientRect(), mx = e.clientX - r.left, my = e.clientY - r.top;
    var f = e.deltaY < 0 ? 1.2 : 1 / 1.2, ns = Math.max(0.1, Math.min(16, scale * f)), k = ns / scale;
    ox = mx - (mx - ox) * k; oy = my - (my - oy) * k; scale = ns; apply();
  }}, {{ passive: false }});
  v.addEventListener('mousedown', function (e) {{
    pressed = true; sx = e.clientX; sy = e.clientY; v.classList.add('dragging'); e.preventDefault();
  }});
  window.addEventListener('mousemove', function (e) {{
    if (!pressed) return;
    ox += e.clientX - sx; oy += e.clientY - sy; sx = e.clientX; sy = e.clientY; apply();
  }});
  window.addEventListener('mouseup', function () {{ pressed = false; v.classList.remove('dragging'); }});
  img.addEventListener('load', fit);
  if (img.complete) fit();
}});
</script>
</body></html>
"""


def main():
    blocks = []
    # world_full first, then regions alphabetically
    def sort_key(p):
        n = os.path.basename(p)[:-4]
        return (0 if n == "world_full" else 1, n)

    files = [p for p in glob.glob(os.path.join(PREV, "*.png"))
             if not os.path.basename(p).startswith("_") and "small" not in p]
    for p in sorted(files, key=sort_key):
        name = os.path.basename(p)[:-4]
        b = base64.b64encode(open(p, "rb").read()).decode()
        title = TITLES.get(name, name)
        blocks.append(
            f'<h2>{title}</h2>\n'
            f'<div class="bar"><button data-z="fit">Fit</button>'
            f'<button data-z="1">1x</button><button data-z="2">2x</button>'
            f'<button data-z="4">4x</button><span class="hint">{os.path.getsize(p)//1024} KB · '
            f'cuộn để zoom</span></div>\n'
            f'<div class="viewer"><img src="data:image/png;base64,{b}"></div>'
        )
        print("added", name)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(HTML.format(blocks="\n".join(blocks)))
    print("wrote", OUT, f"{os.path.getsize(OUT)/1e6:.1f} MB")


if __name__ == "__main__":
    main()
