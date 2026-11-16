"""Render the 3-second answer reveal (artist D — Hime) in the same clean style, transparent background.

Starts from the exact end state of the countdown (title + A B C D row) so the two clips cut together
seamlessly, then fades A/B/C away and brings D to the centre.

Output: output/answer_alpha.mov, answer_alpha.webm, answer_greenscreen.mp4, answer_preview.mp4
"""
import math
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

import make_countdown as mc
from make_countdown import (ARTISTS, F_BOLD, F_MEDIUM, F_SEMI, FPS, GAP, H, HERE, OUT, PINK, ROW_X0, ROW_Y,
                            TILE, TILE_H, TITLE_Y, W, WHITE, ease_in_out, ease_out_quint, paste_center, s,
                            soft_shadow, text_layer)

FRAMES = os.path.join(OUT, "answer_frames")
DUR = 3.0
N = int(FPS * DUR)
ANSWER = 3  # index of D in ARTISTS
ANSWER_NAME = "Hime"

BIG_W, BIG_H = 432, 540  # enlarged answer tile (4:5)
BIG_CY = 960


def make_tile(fn, box, w, h, radius, outline=0):
    size = (s(w), s(h))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), s(radius), fill=255)
    im = Image.open(os.path.join(HERE, "assets", fn)).convert("RGB").crop(box).resize(size, Image.LANCZOS)
    im = im.convert("RGBA")
    im.putalpha(mask)
    return soft_shadow(im, blur=s(20), opacity=0.22, offset=(0, s(8)))


def main():
    shutil.rmtree(FRAMES, ignore_errors=True)
    os.makedirs(FRAMES, exist_ok=True)

    small = [make_tile(fn, box, TILE, TILE_H, 18) for _, fn, box in ARTISTS]
    big = make_tile(ARTISTS[ANSWER][1], ARTISTS[ANSWER][2], BIG_W, BIG_H, 26)
    k_small = TILE / BIG_W

    f_label = ImageFont.truetype(F_SEMI, s(40))
    labels = [soft_shadow(text_layer(lbl, f_label, WHITE), blur=s(10), opacity=0.3) for lbl, _, _ in ARTISTS]

    q1 = soft_shadow(text_layer("Đoán xem là", ImageFont.truetype(F_MEDIUM, s(58)), WHITE, s(1)))
    q2 = soft_shadow(text_layer("artist nào?", ImageFont.truetype(F_BOLD, s(104)), PINK, -s(2)))
    a1 = soft_shadow(text_layer("Đáp án là", ImageFont.truetype(F_MEDIUM, s(58)), WHITE, s(1)))
    a2 = soft_shadow(text_layer(ANSWER_NAME, ImageFont.truetype(F_BOLD, s(120)), PINK, -s(2)))
    tag = soft_shadow(text_layer("D", ImageFont.truetype(F_SEMI, s(46)), WHITE), blur=s(10), opacity=0.3)

    for i in range(N):
        t = i / FPS
        cv = Image.new("RGBA", (s(W), s(H)), (0, 0, 0, 0))

        # --- title swap: question fades up & out, answer fades up & in
        out_p = ease_in_out((t - 0.15) / 0.35)
        in1 = ease_out_quint((t - 0.45) / 0.55)
        in2 = ease_out_quint((t - 0.95) / 0.6)
        paste_center(cv, q1, s(W / 2), s(TITLE_Y - 62 - 20 * out_p), alpha=1 - out_p)
        paste_center(cv, q2, s(W / 2), s(TITLE_Y + 24 - 20 * out_p), alpha=1 - out_p)
        paste_center(cv, a1, s(W / 2), s(TITLE_Y - 62 + 20 * (1 - in1)), alpha=in1)
        name_sc = 0.9 + 0.1 * in2
        paste_center(cv, a2, s(W / 2), s(TITLE_Y + 30 + 20 * (1 - in2)), scale=name_sc, alpha=in2)

        # --- wrong answers fade out and sink
        fade = ease_in_out((t - 0.1) / 0.45)
        for k in range(4):
            if k == ANSWER:
                continue
            cx = ROW_X0 + k * (TILE + GAP) + TILE / 2
            cy = ROW_Y + TILE_H / 2 + 30 * fade
            paste_center(cv, small[k], s(cx), s(cy), scale=1 - 0.06 * fade, alpha=1 - fade)
            paste_center(cv, labels[k], s(cx), s(ROW_Y + TILE_H + 44 + 30 * fade), alpha=1 - fade)

        # --- answer tile moves to centre and grows
        m = ease_out_quint((t - 0.35) / 0.9)
        x0 = ROW_X0 + ANSWER * (TILE + GAP) + TILE / 2
        y0 = ROW_Y + TILE_H / 2
        cx = x0 + (W / 2 - x0) * m
        cy = y0 + (BIG_CY - y0) * m
        breathe = 1 + 0.012 * math.sin((t - 1.3) * 2 * math.pi * 0.7) * ease_in_out((t - 1.3) / 0.4)
        sc = (k_small + (1 - k_small) * m) * breathe
        # small label "D" fades out while moving, the big tag fades in under the tile
        paste_center(cv, labels[ANSWER], s(x0), s(ROW_Y + TILE_H + 44), alpha=1 - ease_in_out((t - 0.3) / 0.3))

        # pink glow ring behind the tile once it lands
        g = ease_out_quint((t - 1.0) / 0.6)
        if g > 0.01:
            gw, gh = BIG_W * sc + 2 * 9, BIG_H * sc + 2 * 9
            ring = Image.new("RGBA", (s(gw) + s(4), s(gh) + s(4)), (0, 0, 0, 0))
            ImageDraw.Draw(ring).rounded_rectangle((s(2), s(2), s(2) + s(gw), s(2) + s(gh)), s(32),
                                                   outline=PINK + (int(255 * g),), width=s(4))
            paste_center(cv, ring, s(cx), s(cy))
        paste_center(cv, big, s(cx), s(cy), scale=sc)

        pt = ease_out_quint((t - 1.15) / 0.55)
        paste_center(cv, tag, s(W / 2), s(BIG_CY + BIG_H / 2 + 62 + 16 * (1 - pt)), alpha=pt)

        cv.resize((W, H), Image.LANCZOS).save(os.path.join(FRAMES, f"f_{i:03d}.png"))

    mc.encode(FRAMES, "answer", DUR)
    print("done", N, "frames")


if __name__ == "__main__":
    main()
