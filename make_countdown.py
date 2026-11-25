"""Render a 3-second transparent "Đoán xem là artist nào?" countdown for Instagram Reels.

Clean / minimal style: white + pastel pink, no text stroke, borderless rounded frames.

Output (1080x1920, 30fps, transparent background):
  output/frames/*.png               PNG sequence with alpha
  output/countdown_alpha.mov        ProRes 4444 with alpha (Premiere, Final Cut, CapCut desktop, DaVinci)
  output/countdown_alpha.webm       VP9 with alpha
  output/countdown_greenscreen.mp4  Green background for chroma key (CapCut mobile, InShot...)
  output/preview.mp4                Preview over a dark background
"""
import math
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

W, H = 1080, 1920
SS = 2  # supersampling factor
FPS = 30
DUR = 3.0
N = int(FPS * DUR)

FONTS = "/usr/share/fonts/opentype/inter/"
F_MEDIUM = FONTS + "InterDisplay-Medium.otf"
F_SEMI = FONTS + "InterDisplay-SemiBold.otf"
F_BOLD = FONTS + "InterDisplay-Bold.otf"

WHITE = (255, 255, 255)
PINK = (248, 200, 218)  # pastel pink

# label -> (image, crop box)  — full 4:5 portrait so the artist name stays readable
SETS = {
    "set1": {  # answer: D - Hime
        "prefix": "",
        "answer": 3,
        "answer_name": "Hime",
        "artists": [
            ("A", "A.jpg", (112, 0, 976, 1080)),
            ("B", "B.jpg", (112, 5, 968, 1075)),
            ("C", "C.jpg", (112, 0, 968, 1070)),
            ("D", "D.jpg", (112, 0, 968, 1070)),
        ],
    },
    "set2": {  # answer: D - Phương Vy
        "prefix": "set2_",
        "answer": 3,
        "answer_name": "Phương Vy",
        "artists": [
            ("A", "set2/A.png", (0, 0, 1040, 1300)),
            ("B", "set2/B.png", (0, 0, 1036, 1295)),
            ("C", "set2/C.png", (0, 0, 1028, 1285)),
            ("D", "set2/D.png", (0, 0, 1044, 1305)),
        ],
    },
}
SET = os.environ.get("ARTIST_SET", "set1")  # run with ARTIST_SET=set2 for the second quiz
CFG = SETS[SET]
PREFIX = CFG["prefix"]
ARTISTS = CFG["artists"]

# layout (1x coordinates)
TILE = 236  # width
TILE_H = 295  # height (4:5)
GAP = 16
ROW_Y = 720
ROW_X0 = (W - (4 * TILE + 3 * GAP)) // 2
TITLE_Y = 540
RING_CY = 1300
RING_R = 112


def clamp01(t):
    return max(0.0, min(1.0, t))


def ease_out_cubic(t):
    return 1 - (1 - clamp01(t)) ** 3


def ease_out_quint(t):
    return 1 - (1 - clamp01(t)) ** 5


def ease_in_out(t):
    t = clamp01(t)
    return t * t * (3 - 2 * t)


def s(v):
    return int(round(v * SS))


def soft_shadow(layer, blur=s(18), opacity=0.28, offset=(0, s(4))):
    """Add a very soft drop shadow (no stroke) so white text stays legible on light footage."""
    pad = blur * 3
    big = Image.new("RGBA", (layer.size[0] + 2 * pad, layer.size[1] + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(layer, (pad, pad))
    a = big.getchannel("A").point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", big.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    out.alpha_composite(big)
    return out


def text_layer(text, font, fill, tracking=0):
    """Text with optional letter spacing (tracking in px at SS scale)."""
    widths = [font.getlength(ch) for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    asc, desc = font.getmetrics()
    pad = s(20)
    im = Image.new("RGBA", (int(total) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x = pad
    for ch, w in zip(text, widths):
        d.text((x, pad), ch, font=font, fill=fill)
        x += w + tracking
    return im.crop(im.getbbox()) if im.getbbox() else im


def load_tiles():
    tiles = []
    size = (s(TILE), s(TILE_H))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), s(18), fill=255)
    for label, fn, box in ARTISTS:
        im = Image.open(os.path.join(HERE, "assets", fn)).convert("RGB")
        im = im.crop(box).resize(size, Image.LANCZOS).convert("RGBA")
        im.putalpha(mask)
        tiles.append((label, soft_shadow(im, blur=s(20), opacity=0.22, offset=(0, s(8)))))
    return tiles


def paste_center(canvas, layer, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    lw, lh = layer.size
    if abs(scale - 1.0) > 1e-3:
        layer = layer.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.BICUBIC)
    if alpha < 1.0:
        layer = layer.copy()
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * alpha)))
    x = int(cx - layer.size[0] / 2)
    y = int(cy - layer.size[1] / 2)
    canvas.alpha_composite(layer, (max(0, x), max(0, y)), (max(0, -x), max(0, -y)))


FRAMES = os.path.join(OUT, PREFIX + "frames")


def main():
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES, exist_ok=True)

    tiles = load_tiles()

    title1 = soft_shadow(text_layer("Đoán xem là", ImageFont.truetype(F_MEDIUM, s(58)), WHITE, s(1)))
    title2 = soft_shadow(text_layer("artist nào?", ImageFont.truetype(F_BOLD, s(104)), PINK, -s(2)))

    f_label = ImageFont.truetype(F_SEMI, s(40))
    labels = [soft_shadow(text_layer(lbl, f_label, WHITE), blur=s(10), opacity=0.3) for lbl, _ in tiles]

    f_num = ImageFont.truetype(F_SEMI, s(150))
    nums = {n: soft_shadow(text_layer(str(n), f_num, WHITE), blur=s(16), opacity=0.25) for n in (3, 2, 1)}

    for i in range(N):
        t = i / FPS
        cv = Image.new("RGBA", (s(W), s(H)), (0, 0, 0, 0))

        # --- title: gentle fade + rise
        p1 = ease_out_quint(t / 0.5)
        p2 = ease_out_quint((t - 0.08) / 0.5)
        paste_center(cv, title1, s(W / 2), s(TITLE_Y - 62 + 24 * (1 - p1)), alpha=p1)
        paste_center(cv, title2, s(W / 2), s(TITLE_Y + 24 + 24 * (1 - p2)), alpha=p2)

        # --- tiles: staggered fade + rise, slight scale settle
        for k, (lbl, tile) in enumerate(tiles):
            p = ease_out_quint((t - 0.15 - k * 0.08) / 0.6)
            cx = ROW_X0 + k * (TILE + GAP) + TILE / 2
            cy = ROW_Y + TILE_H / 2 + 40 * (1 - p)
            paste_center(cv, tile, s(cx), s(cy), scale=0.94 + 0.06 * p, alpha=p)
            pl = ease_out_quint((t - 0.35 - k * 0.08) / 0.5)
            paste_center(cv, labels[k], s(cx), s(ROW_Y + TILE_H + 44 + 12 * (1 - pl)), alpha=pl)

        # --- countdown ring: thin pink line draining over 3s
        ring_in = ease_out_cubic(t / 0.4)
        r = s(RING_R)
        cx, cy = s(W / 2), s(RING_CY)
        lw = s(5)
        ring = Image.new("RGBA", cv.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ring)
        box = (cx - r, cy - r, cx + r, cy + r)
        dr.ellipse(box, outline=WHITE + (int(85 * ring_in),), width=lw)
        remain = max(0.0, 1 - t / DUR)
        if remain > 0:
            col = PINK + (int(255 * ring_in),)
            dr.arc(box, -90, -90 + 360 * remain, fill=col, width=lw)
            rr = r - lw / 2
            for ang in (-90, -90 + 360 * remain):  # round caps
                a = math.radians(ang)
                hx, hy = cx + rr * math.cos(a), cy + rr * math.sin(a)
                dr.ellipse((hx - lw / 2, hy - lw / 2, hx + lw / 2, hy + lw / 2), fill=col)
        cv.alpha_composite(ring)

        # --- number: soft scale-down + fade each second
        n = 3 - int(t)
        lt = t - int(t)
        p = ease_out_quint(lt / 0.35)
        sc = 1.18 - 0.18 * p
        al = p if lt < 0.8 else max(0.0, 1 - ease_in_out((lt - 0.8) / 0.2))
        if lt >= 0.8:
            sc -= 0.06 * ease_in_out((lt - 0.8) / 0.2)
        if n >= 1:
            paste_center(cv, nums[n], cx, cy, scale=sc, alpha=al)

        cv.resize((W, H), Image.LANCZOS).save(os.path.join(FRAMES, f"f_{i:03d}.png"))

    encode(FRAMES, PREFIX + "countdown")
    print("done", N, "frames")


def encode(frames_dir, prefix, dur=DUR):
    seq = os.path.join(frames_dir, "f_%03d.png")
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", seq]
    subprocess.run(ff + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                         "-vendor", "apl0", os.path.join(OUT, f"{prefix}_alpha.mov")], check=True)
    subprocess.run(ff + ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "4M", "-auto-alt-ref", "0",
                         os.path.join(OUT, f"{prefix}_alpha.webm")], check=True)
    for name, color in ((f"{prefix}_greenscreen.mp4", "0x00FF00"), (f"{prefix}_bg_3a3a46.mp4", "0x3a3a46")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={FPS}:d={dur}",
                        "-framerate", str(FPS), "-i", seq,
                        "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p",
                        "-c:v", "libx264", "-crf", "16", "-movflags", "+faststart",
                        os.path.join(OUT, name)], check=True)


if __name__ == "__main__":
    main()
