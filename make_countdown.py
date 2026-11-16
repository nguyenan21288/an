"""Render a 3-second transparent "Đoán xem là artist nào?" countdown for Instagram Reels.

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
FRAMES = os.path.join(OUT, "frames")

W, H = 1080, 1920
SS = 2  # supersampling factor
FPS = 30
DUR = 3.0
N = int(FPS * DUR)

FONT_BLACK = "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf"
FONT_BOLD = "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf"

# label -> (image, crop box)  — full 4:5 portrait so the artist name stays readable
ARTISTS = [
    ("A", "A.jpg", (112, 0, 976, 1080)),
    ("B", "B.jpg", (112, 5, 968, 1075)),
    ("C", "C.jpg", (112, 0, 968, 1070)),
    ("D", "D.jpg", (112, 0, 968, 1070)),
]
ACCENT = [(255, 214, 10), (255, 214, 10), (255, 214, 10), (255, 214, 10)]
YELLOW = (255, 214, 10)

# layout (1x coordinates)
TILE = 236  # width
TILE_H = 295  # height (4:5)
GAP = 16
ROW_Y = 720
ROW_X0 = (W - (4 * TILE + 3 * GAP)) // 2
TITLE_Y = 520
RING_CY = 1330
RING_R = 150


def ease_out_back(t, s=1.7):
    t = max(0.0, min(1.0, t)) - 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def s(v):
    return int(round(v * SS))


def load_tiles():
    tiles = []
    size = (s(TILE), s(TILE_H))
    radius = s(22)
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    for label, fn, box in ARTISTS:
        im = Image.open(os.path.join(HERE, "assets", fn)).convert("RGB")
        im = im.crop(box).resize(size, Image.LANCZOS).convert("RGBA")
        im.putalpha(mask)
        # white border
        border = s(7)
        framed = Image.new("RGBA", (size[0] + 2 * border, size[1] + 2 * border), (0, 0, 0, 0))
        bmask = Image.new("L", framed.size, 0)
        ImageDraw.Draw(bmask).rounded_rectangle(
            (0, 0, framed.size[0] - 1, framed.size[1] - 1), radius + border, fill=255
        )
        framed.paste(Image.new("RGBA", framed.size, (255, 255, 255, 255)), (0, 0), bmask)
        framed.alpha_composite(im, (border, border))
        tiles.append((label, framed))
    return tiles


def shadow_of(layer, blur, opacity=0.55, offset=(0, 0)):
    a = layer.getchannel("A").point(lambda v: int(v * opacity))
    sh = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    sh.putalpha(a)
    sh = sh.filter(ImageFilter.GaussianBlur(blur))
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.alpha_composite(sh, offset)
    return out


def text_layer(text, font, fill, stroke=0, stroke_fill=(0, 0, 0)):
    bbox = font.getbbox(text, stroke_width=stroke)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = s(30)
    im = Image.new("RGBA", (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(im).text(
        (pad - bbox[0], pad - bbox[1]), text, font=font, fill=fill,
        stroke_width=stroke, stroke_fill=stroke_fill,
    )
    return im


def paste_center(canvas, layer, cx, cy, scale=1.0, alpha=1.0, rot=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    lw, lh = layer.size
    if scale != 1.0:
        layer = layer.resize((max(1, int(lw * scale)), max(1, int(lh * scale))), Image.BICUBIC)
    if rot:
        layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1.0:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    x = int(cx - layer.size[0] / 2)
    y = int(cy - layer.size[1] / 2)
    canvas.alpha_composite(layer, (max(0, x), max(0, y)),
                           (max(0, -x), max(0, -y)))


def with_shadow(layer, blur=s(14), opacity=0.6, offset=(0, s(6))):
    pad = blur * 3
    big = Image.new("RGBA", (layer.size[0] + 2 * pad, layer.size[1] + 2 * pad), (0, 0, 0, 0))
    big.alpha_composite(layer, (pad, pad))
    out = shadow_of(big, blur, opacity, offset)
    out.alpha_composite(big)
    return out


def main():
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES, exist_ok=True)

    tiles = [(lbl, with_shadow(t)) for lbl, t in load_tiles()]

    f_title = ImageFont.truetype(FONT_BLACK, s(84))
    f_sub = ImageFont.truetype(FONT_BLACK, s(112))
    f_label = ImageFont.truetype(FONT_BLACK, s(52))
    f_num = ImageFont.truetype(FONT_BLACK, s(210))

    title1 = with_shadow(text_layer("ĐOÁN XEM LÀ", f_title, (255, 255, 255), s(8), (0, 0, 0)))
    title2 = with_shadow(text_layer("ARTIST NÀO?", f_sub, YELLOW, s(9), (0, 0, 0)))

    # label badges (circle + letter)
    badges = []
    bd = s(78)
    for lbl, _ in tiles:
        b = Image.new("RGBA", (bd + s(20), bd + s(20)), (0, 0, 0, 0))
        d = ImageDraw.Draw(b)
        d.ellipse((s(10), s(10), s(10) + bd, s(10) + bd), fill=YELLOW, outline=(0, 0, 0), width=s(5))
        bb = f_label.getbbox(lbl)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        d.text((s(10) + (bd - tw) / 2 - bb[0], s(10) + (bd - th) / 2 - bb[1]), lbl, font=f_label, fill=(0, 0, 0))
        badges.append(with_shadow(b, blur=s(8), opacity=0.5, offset=(0, s(4))))

    nums = {n: with_shadow(text_layer(str(n), f_num, (255, 255, 255), s(10), (0, 0, 0)), blur=s(16))
            for n in (3, 2, 1)}

    for i in range(N):
        t = i / FPS
        cv = Image.new("RGBA", (s(W), s(H)), (0, 0, 0, 0))

        # --- title: drops in, then breathes slightly
        p1 = ease_out_back((t - 0.0) / 0.35)
        p2 = ease_out_back((t - 0.08) / 0.35)
        pulse = 1 + 0.03 * math.sin(t * 2 * math.pi * 1.5) if t > 0.45 else 1
        paste_center(cv, title1, s(W / 2), s(TITLE_Y - 40) - s(60) * (1 - p1), scale=p1, alpha=min(1, p1 * 1.5))
        paste_center(cv, title2, s(W / 2), s(TITLE_Y + 60) - s(60) * (1 - p2), scale=p2 * pulse, alpha=min(1, p2 * 1.5))

        # --- tiles: staggered pop-in, gentle float
        for k, (lbl, tile) in enumerate(tiles):
            p = ease_out_back((t - 0.12 - k * 0.07) / 0.4, 2.2)
            cx = ROW_X0 + k * (TILE + GAP) + TILE / 2
            cy = ROW_Y + TILE_H / 2 + 8 * math.sin(t * 2 * math.pi * 0.8 + k * 0.9) * min(1, max(0, t - 0.6) * 3)
            rot = (1 - p) * (-12 if k % 2 == 0 else 12)
            paste_center(cv, tile, s(cx), s(cy), scale=p, alpha=min(1, p * 1.5), rot=rot)
            pb = ease_out_back((t - 0.3 - k * 0.07) / 0.35, 2.5)
            paste_center(cv, badges[k], s(cx), s(ROW_Y + TILE_H + 34), scale=pb)

        # --- countdown ring: drains over 3s
        ring_in = ease_out_cubic(t / 0.3)
        r = s(RING_R) * (0.6 + 0.4 * ring_in)
        cx, cy = s(W / 2), s(RING_CY)
        ring = Image.new("RGBA", cv.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(ring)
        box = (cx - r, cy - r, cx + r, cy + r)
        dr.ellipse(box, fill=(0, 0, 0, int(110 * ring_in)))
        dr.ellipse(box, outline=(255, 255, 255, int(70 * ring_in)), width=s(16))
        remain = max(0.0, 1 - t / DUR)
        if remain > 0:
            dr.arc(box, -90, -90 + 360 * remain, fill=YELLOW + (int(255 * ring_in),), width=s(16))
            # rounded cap at the head
            ang = math.radians(-90 + 360 * remain)
            rr = r - s(8)
            hx, hy = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
            dr.ellipse((hx - s(8), hy - s(8), hx + s(8), hy + s(8)), fill=YELLOW + (int(255 * ring_in),))
            dr.ellipse((cx - s(8), cy - rr - s(8), cx + s(8), cy - rr + s(8)), fill=YELLOW + (int(255 * ring_in),))
        cv.alpha_composite(ring)

        # --- number: punch-in each second
        n = 3 - int(t)
        lt = t - int(t)
        sc = ease_out_back(lt / 0.28, 3.0)
        if lt > 0.82:  # quick shrink-out before next number
            sc *= 1 - ease_out_cubic((lt - 0.82) / 0.18) * 0.35
        al = 1.0 if lt <= 0.85 else max(0.0, 1 - (lt - 0.85) / 0.15)
        if n >= 1:
            paste_center(cv, nums[n], cx, cy + s(4), scale=sc, alpha=al)

        cv.resize((W, H), Image.LANCZOS).save(os.path.join(FRAMES, f"f_{i:03d}.png"))

    seq = os.path.join(FRAMES, "f_%03d.png")
    ff = ["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", seq]
    subprocess.run(ff + ["-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                         "-vendor", "apl0", os.path.join(OUT, "countdown_alpha.mov")], check=True)
    subprocess.run(ff + ["-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "4M", "-auto-alt-ref", "0",
                         os.path.join(OUT, "countdown_alpha.webm")], check=True)
    for name, color in (("countdown_greenscreen.mp4", "0x00FF00"), ("preview.mp4", "0x3a3a46")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-f", "lavfi", "-i", f"color=c={color}:s={W}x{H}:r={FPS}:d={DUR}",
                        "-framerate", str(FPS), "-i", seq,
                        "-filter_complex", "[0][1]overlay=shortest=1,format=yuv420p",
                        "-c:v", "libx264", "-crf", "16", "-movflags", "+faststart",
                        os.path.join(OUT, name)], check=True)
    print("done", N, "frames")


if __name__ == "__main__":
    main()
