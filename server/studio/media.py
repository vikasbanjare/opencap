"""Local, free media operations used by Studio tools: grading, layout, crops, PDFs and ffmpeg assembly.
No model calls here; everything is Pillow, numpy or ffmpeg."""
from __future__ import annotations

import json, math, subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .providers import ProviderError


def sh(cmd: list[str], timeout: int = 1800) -> subprocess.CompletedProcess:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise ProviderError(f"{cmd[0]} failed: {r.stderr[-600:]}")
    return r


def probe(p: Path) -> dict:
    j = json.loads(sh(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", str(p)]).stdout or "{}")
    v = next((s for s in j.get("streams", []) if s.get("codec_type") == "video"), {})
    return {"width": int(v.get("width", 0)), "height": int(v.get("height", 0)), "duration": float(j.get("format", {}).get("duration", 0) or 0),
            "hasAudio": any(s.get("codec_type") == "audio" for s in j.get("streams", []))}


def font(size: int, bold: bool = True):
    for name in (["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"] if bold else ["DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default(size)  # Pillow >= 10.1 scales the built-in font


def wrap(d: ImageDraw.ImageDraw, text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) > width and cur:
            lines.append(cur); cur = w
        else:
            cur = t
    if cur: lines.append(cur)
    return lines


# ---------- colour grading (pixel maths) ----------

GRADE_PRESETS = {
    "None": {},
    "Natural": {"contrast": 5, "saturation": 5},
    "Cinematic": {"contrast": 18, "saturation": -8, "split": 35, "temp": 4, "bloom": 15},
    "B&W Film": {"saturation": -100, "contrast": 25, "grain": 35},
    "Split Tone": {"split": 60},
    "Soft Skin": {"soften": 35, "temp": 6, "contrast": -5},
    "16mm Film": {"grain": 55, "halation": 35, "contrast": 10, "saturation": -10, "temp": 8},
    "Old Lens": {"bloom": 40, "vignette": 45, "soften": 20, "contrast": -8},
    "Teal & Orange": {"split": 70, "contrast": 12, "saturation": 10},
    "Noir": {"saturation": -100, "contrast": 45, "vignette": 50, "exposure": -0.3},
    "Pastel": {"contrast": -18, "saturation": -25, "exposure": 0.3, "temp": 3},
    "Warm": {"temp": 25, "saturation": 5},
    "Vintage": {"temp": 18, "contrast": -10, "saturation": -20, "grain": 25, "vignette": 25},
}


def grade(im: Image.Image, temp=0.0, hue=0.0, saturation=0.0, contrast=0.0, split=0.0, exposure=0.0,
          soften=0.0, bloom=0.0, halation=0.0, grain=0.0, vignette=0.0) -> Image.Image:
    """Sliders are -100..100 (exposure in stops, -2..2); effects are 0..100."""
    a = np.asarray(im.convert("RGB")).astype(np.float32) / 255
    if soften:
        b = np.asarray(im.convert("RGB").filter(ImageFilter.GaussianBlur(2 + soften / 20))).astype(np.float32) / 255
        a = a * (1 - soften / 160) + b * (soften / 160)
    a = a * (2 ** exposure)
    if temp:
        a[..., 0] *= 1 + temp / 300; a[..., 2] *= 1 - temp / 300
    lum = (a * [0.299, 0.587, 0.114]).sum(-1, keepdims=True)
    if split:  # teal shadows, warm highlights
        k = split / 100
        a += k * 0.08 * ((1 - lum) * np.array([-0.6, 0.15, 0.6]) + lum * np.array([0.6, 0.15, -0.6]))
    if saturation:
        a = lum + (a - lum) * (1 + saturation / 100)
    if hue:
        hsv = np.asarray(Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).convert("HSV")).astype(np.int16)
        hsv[..., 0] = (hsv[..., 0] + int(hue * 1.275)) % 256
        a = np.asarray(Image.fromarray(hsv.astype(np.uint8), "HSV").convert("RGB")).astype(np.float32) / 255
    if contrast:
        a = (a - 0.5) * (1 + contrast / 100) + 0.5
    if bloom or halation:
        hi = np.clip((a - 0.7) / 0.3, 0, 1)
        blur = np.asarray(Image.fromarray((hi * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(a.shape[:2]) / 60))).astype(np.float32) / 255
        a += blur * (bloom / 100) * 0.6
        a[..., 0] += blur[..., 0] * (halation / 100) * 0.7; a[..., 1] += blur[..., 1] * (halation / 100) * 0.15
    if vignette:
        h, w = a.shape[:2]; y, x = np.ogrid[:h, :w]
        r = np.sqrt(((x - w / 2) / (w / 2)) ** 2 + ((y - h / 2) / (h / 2)) ** 2)
        a *= (1 - np.clip(r - 0.4, 0, 1) * (vignette / 100))[..., None]
    if grain:
        a += np.random.default_rng(7).normal(0, grain / 100 * 0.06, a.shape[:2])[..., None]
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


def side_by_side(a: Image.Image, b: Image.Image, labels=("Before", "After")) -> Image.Image:
    h = min(a.height, 900); a = a.resize((int(a.width * h / a.height), h)); b = b.resize((int(b.width * h / b.height), h))
    out = Image.new("RGB", (a.width + b.width + 8, h), "white"); out.paste(a, (0, 0)); out.paste(b, (a.width + 8, 0))
    d = ImageDraw.Draw(out); f = font(max(14, h // 30))
    for x, t in ((12, labels[0]), (a.width + 20, labels[1])):
        d.rounded_rectangle([x, 12, x + d.textlength(t, font=f) + 20, 12 + f.size + 12], 8, fill=(0, 0, 0))
        d.text((x + 10, 18), t, font=f, fill="white")
    return out


def palette(images: list[Image.Image], n: int = 6) -> list[str]:
    strip = Image.new("RGB", (200 * len(images), 200))
    for i, im in enumerate(images):
        strip.paste(ImageOps.fit(im.convert("RGB"), (200, 200)), (200 * i, 0))
    q = strip.quantize(colors=n, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette()[: n * 3]; counts = sorted(q.getcolors(), reverse=True)
    return ["#%02x%02x%02x" % tuple(pal[i * 3: i * 3 + 3]) for _, i in counts]


def swatches(colors: list[str], w: int = 1200) -> Image.Image:
    im = Image.new("RGB", (w, 360), "white"); d = ImageDraw.Draw(im); sw = w // max(1, len(colors)); f = font(22)
    for i, c in enumerate(colors):
        d.rectangle([i * sw, 0, (i + 1) * sw, 280], fill=c); d.text((i * sw + 16, 300), c.upper(), font=f, fill="black")
    return im


# ---------- crops, canvases, layouts ----------

def smart_crop(im: Image.Image, w: int, h: int, focus: str = "Center") -> Image.Image:
    cx = {"Left": 0.0, "Right": 1.0}.get(focus, 0.5)
    return ImageOps.fit(im.convert("RGB"), (w, h), Image.LANCZOS, centering=(cx, 0.5))


def extend_canvas(im: Image.Image, w: int, h: int, focus: str = "Center") -> tuple[Image.Image, Image.Image]:
    """Fit the whole image inside w×h over a blurred fill. Returns (canvas, mask of the new area) for an outpaint pass."""
    im = im.convert("RGB"); s = min(w / im.width, h / im.height)
    fg = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    bg = ImageOps.fit(im, (w, h)).filter(ImageFilter.GaussianBlur(40))
    x = {"Left": 0, "Right": w - fg.width}.get(focus, (w - fg.width) // 2); y = (h - fg.height) // 2
    bg.paste(fg, (x, y))
    mask = Image.new("L", (w, h), 255); ImageDraw.Draw(mask).rectangle([x, y, x + fg.width - 1, y + fg.height - 1], fill=0)
    return bg, mask


def overlay_title(im: Image.Image, title: str, sub: str = "", where: str = "bottom", color="white") -> Image.Image:
    im = im.convert("RGB"); d = ImageDraw.Draw(im, "RGBA"); W, H = im.size
    f = font(max(24, int(min(W, H) * (0.11 if len(title) < 18 else 0.07)))); fs = font(max(14, int(min(W, H) * 0.035)), bold=False)
    lines = wrap(d, title.upper(), f, int(W * 0.88)); lh = f.size * 1.08
    block = lh * len(lines) + (fs.size * 1.8 if sub else 0)
    y = H * 0.08 if where == "top" else H - block - H * 0.07
    d.rectangle([0, y - H * 0.04, W, y + block + H * 0.04], fill=(0, 0, 0, 110))
    for ln in lines:
        x = (W - d.textlength(ln, font=f)) / 2
        d.text((x, y), ln, font=f, fill=color, stroke_width=max(2, f.size // 18), stroke_fill="black"); y += lh
    if sub:
        d.text(((W - d.textlength(sub, font=fs)) / 2, y + fs.size * 0.4), sub, font=fs, fill=(235, 235, 235))
    return im


def end_plate(size: tuple[int, int], product: str, price: str, caption: str, cta: str, image: Image.Image | None = None, accent="#C6F24E") -> Image.Image:
    W, H = size; im = Image.new("RGB", size, (14, 14, 18)); d = ImageDraw.Draw(im)
    if image:
        p = ImageOps.contain(image.convert("RGBA"), (int(W * 0.6), int(H * 0.45))); im.paste(p, ((W - p.width) // 2, int(H * 0.08)), p)
    y = H * 0.58; big, mid = font(int(min(W, H) * 0.08)), font(int(min(W, H) * 0.045), bold=False)
    for t, f, c in ((product, big, "white"), (price, big, accent), (caption, mid, (200, 200, 210))):
        if not t: continue
        for ln in wrap(d, t, f, int(W * 0.86)):
            d.text(((W - d.textlength(ln, font=f)) / 2, y), ln, font=f, fill=c); y += f.size * 1.2
    if cta:
        f = font(int(min(W, H) * 0.05)); tw = d.textlength(cta, font=f)
        x0, y0 = (W - tw) / 2 - 30, H * 0.86
        d.rounded_rectangle([x0, y0, x0 + tw + 60, y0 + f.size + 30], 40, fill=accent); d.text((x0 + 30, y0 + 13), cta, font=f, fill=(20, 24, 10))
    return im


def grid(images: list[Image.Image], cols: int, cell: tuple[int, int], gap: int = 12, captions: list[str] | None = None, bg="white") -> Image.Image:
    rows = math.ceil(len(images) / cols); cap_h = 70 if captions else 0
    out = Image.new("RGB", (cols * cell[0] + (cols + 1) * gap, rows * (cell[1] + cap_h) + (rows + 1) * gap), bg); d = ImageDraw.Draw(out); f = font(18, bold=False)
    for i, im in enumerate(images):
        x, y = gap + (i % cols) * (cell[0] + gap), gap + (i // cols) * (cell[1] + cap_h + gap)
        out.paste(ImageOps.fit(im.convert("RGB"), cell), (x, y)); d.rectangle([x, y, x + cell[0] - 1, y + cell[1] - 1], outline="black", width=2)
        if captions and i < len(captions):
            for k, ln in enumerate(wrap(d, captions[i], f, cell[0])[:3]):
                d.text((x, y + cell[1] + 6 + k * 21), ln, font=f, fill="black")
    return out


def comic_page(panels: list[tuple[Image.Image, list[str], str]], size=(1600, 2300), title: str = "", style_bg="white") -> Image.Image:
    """panels: (art, dialogue lines, sfx). Lays panels out in rows of 1–2, draws caption boxes and SFX."""
    W, H = size; m = 30; top = 90 if title else m
    page = Image.new("RGB", size, style_bg); d = ImageDraw.Draw(page)
    if title:
        d.text((m, 24), title, font=font(46), fill="black")
    n = len(panels); rows = []; i = 0
    while i < n:
        take = 1 if (n - i) == 1 or (len(rows) % 3 == 0 and n - i > 2 and n % 2) else 2
        rows.append(panels[i:i + take]); i += take
    rh = (H - top - m * (len(rows) + 1) + m) / len(rows)
    y = top
    for row in rows:
        pw = (W - m * (len(row) + 1)) / len(row)
        for k, (art, lines, sfx) in enumerate(row):
            x = m + k * (pw + m); box = (int(pw), int(rh))
            page.paste(ImageOps.fit(art.convert("RGB"), box), (int(x), int(y)))
            d.rectangle([x, y, x + pw, y + rh], outline="black", width=6)
            fy = y + 14; f = font(max(18, int(min(pw, rh) * 0.045)), bold=False)
            for ln in lines[:3]:
                wl = wrap(d, ln, f, int(pw * 0.62))
                bh = len(wl) * f.size * 1.2 + 18; bw = max(d.textlength(t, font=f) for t in wl) + 28
                d.rounded_rectangle([x + 14, fy, x + 14 + bw, fy + bh], 18, fill="white", outline="black", width=3)
                for j, t in enumerate(wl):
                    d.text((x + 28, fy + 9 + j * f.size * 1.2), t, font=f, fill="black")
                fy += bh + 10
            if sfx:
                fs = font(max(28, int(min(pw, rh) * 0.1)))
                d.text((x + pw - d.textlength(sfx, font=fs) - 24, y + rh - fs.size - 24), sfx, font=fs, fill=(255, 214, 0), stroke_width=5, stroke_fill="black")
        y += rh + m
    return page


def to_pdf(pages: list[Image.Image], out: Path) -> Path:
    rgb = [p.convert("RGB") for p in pages]
    rgb[0].save(out, save_all=True, append_images=rgb[1:], resolution=150)
    return out


# ---------- video ----------

def frames(video: Path, out_dir: Path, every: float = 1.0, width: int = 640, limit: int = 400) -> list[tuple[float, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", f"fps=1/{every},scale={width}:-2", "-frames:v", str(limit), str(out_dir / "f%05d.jpg")])
    return [((i) * every, p) for i, p in enumerate(sorted(out_dir.glob("f*.jpg")))]


def frame_at(video: Path, t: float, out: Path) -> Path:
    sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(0, t):.3f}", "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)])
    return out


def sharpness(p: Path) -> float:
    a = np.asarray(Image.open(p).convert("L").resize((320, 180))).astype(np.float32)
    return float(np.abs(np.diff(a, axis=0)).mean() + np.abs(np.diff(a, axis=1)).mean())


def motion_scores(fr: list[tuple[float, Path]]) -> list[float]:
    prev, out = None, []
    for _, p in fr:
        a = np.asarray(Image.open(p).convert("L").resize((160, 90))).astype(np.float32)
        out.append(0.0 if prev is None else float(np.abs(a - prev).mean())); prev = a
    return out


def norm_clip(src: Path, out: Path, w: int, h: int, start: float | None = None, dur: float | None = None, fps: int = 30) -> Path:
    """Scale/crop to w×h, fixed fps, always with a stereo audio track, so clips concat cleanly."""
    info = probe(src)
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start is not None: cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if not info["hasAudio"]: cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    if dur is not None: cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,format=yuv420p",
            "-map", "0:v:0", "-map", "0:a:0" if info["hasAudio"] else "1:a:0", "-shortest" if not info["hasAudio"] else "-sn",
            "-ar", "48000", "-ac", "2", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", str(out)]
    sh(cmd); return out


def still_clip(img: Path, out: Path, w: int, h: int, dur: float = 3.0) -> Path:
    sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", str(img), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", f"{dur:.3f}",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps=30,setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast",
        "-c:a", "aac", "-ar", "48000", "-ac", "2", "-shortest", str(out)])
    return out


def concat(clips: list[Path], out: Path) -> Path:
    lst = out.with_suffix(".txt"); lst.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    lst.unlink(missing_ok=True); return out


def mix(video: Path, out: Path, voice: Path | None = None, music: Path | None = None, music_db: float = -16) -> Path:
    """Lay a voiceover and a ducked music bed under a video's own audio."""
    ins, parts, labels = ["-i", str(video)], ["[0:a]volume=0.6[a0]"], ["[a0]"]
    k = 1
    if voice:
        ins += ["-i", str(voice)]; parts.append(f"[{k}:a]volume=1.4,apad[vo]"); labels.append("[vo]"); k += 1
    if music:
        ins += ["-stream_loop", "-1", "-i", str(music)]; parts.append(f"[{k}:a]volume={10 ** (music_db / 20):.3f}[mu]"); labels.append("[mu]")
    fc = ";".join(parts) + ";" + "".join(labels) + f"amix=inputs={len(labels)}:duration=first:normalize=0[a]"
    sh(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)])
    return out


def reframe(video: Path, out: Path, ratio: float, height: int, x_pos: float = 0.5) -> Path:
    """Crop (or pad, when the target is wider) to ratio, at `height` lines; x_pos 0..1 picks the crop window."""
    info = probe(video); W, H = info["width"], info["height"]
    oh = height - height % 2; ow = int(round(oh * ratio / 2) * 2)
    if W / H > ratio:  # source wider: crop width
        cw = int(H * ratio) // 2 * 2
        vf = f"crop={cw}:{H // 2 * 2}:{int((W - cw) * x_pos)}:0,scale={ow}:{oh}"
    else:              # source taller: crop height around the middle
        ch = int(W / ratio) // 2 * 2
        vf = f"crop={W // 2 * 2}:{ch}:0:{(H - ch) // 2},scale={ow}:{oh}"
    sh(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vf", vf + ",setsar=1,format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-c:a", "aac", "-movflags", "+faststart", str(out)])
    return out


def saliency_x(video: Path, tmp: Path) -> float:
    """Horizontal centre of edge energy across sampled frames: a cheap stand-in for subject tracking."""
    fr = frames(video, tmp, every=max(0.5, probe(video)["duration"] / 24), width=320, limit=24)
    xs = []
    for _, p in fr:
        a = np.asarray(Image.open(p).convert("L").filter(ImageFilter.FIND_EDGES)).astype(np.float32)
        col = a.sum(0); xs.append(float((col * np.arange(col.size)).sum() / max(1, col.sum()) / col.size))
    return float(np.median(xs)) if xs else 0.5
