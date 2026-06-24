from __future__ import annotations
import os
import io
import subprocess
import tempfile
import requests
from PIL import Image, ImageDraw, ImageFont
from config import BRAND, SLIDE_DIMENSIONS, SECONDS_PER_SLIDE, FPS

W, H = SLIDE_DIMENSIONS
EMERALD = (26, 77, 46)      # #1A4D2E
GOLD    = (184, 212, 94)    # #B8D45E
WHITE   = (255, 255, 255)
BLACK   = (10, 10, 10)
PAD     = 80                # horizontal padding


def fetch_image(query: str, unsplash_key: str, page: int = 1) -> Image.Image | None:
    try:
        # Use search endpoint for consistent, relevant results
        url = "https://api.unsplash.com/search/photos"
        params = {
            "query": query,
            "orientation": "portrait",
            "content_filter": "high",
            "per_page": 5,
            "page": page,
        }
        headers = {"Authorization": f"Client-ID {unsplash_key}"}
        r = requests.get(url, params=params, headers=headers, timeout=8)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                import random as _r
                pick = _r.choice(results[:5])
                img_url = pick["urls"]["regular"]
                img_data = requests.get(img_url, timeout=10).content
                return Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception:
        pass
    return None


# Curated per-slide queries — always relevant to phones, hygiene, lifestyle
SLIDE_IMAGE_QUERIES = [
    # Hook — dirty phone, smudge, grime
    ["dirty smartphone screen close up", "phone screen smudge fingerprint", "person holding dirty phone"],
    # Slide 1 — bacteria, germ, gross reality
    ["bacteria microscope", "dirty hands touching phone", "smudged phone screen macro"],
    # Slide 2 — phone use lifestyle
    ["woman scrolling phone bed", "man using phone commute", "person touching phone screen"],
    # Slide 3 — product / clean / nature (plant-based / alcohol / clean)
    ["clean phone screen", "plant leaf minimal", "natural ingredients skincare"],
    # Slide 4 — price / value / coins
    ["coins change close up", "chewing gum pack", "coffee cup price"],
    # CTA — clean phone, order, shop
    ["clean smartphone desk minimal", "phone wipe clean screen", "minimalist product lifestyle"],
]


def resize_crop(img: Image.Image, size: tuple) -> Image.Image:
    tw, th = size
    r = img.width / img.height
    tr = tw / th
    if r > tr:
        nw, nh = int(th * r), th
    else:
        nw, nh = tw, int(tw / r)
    img = img.resize((nw, nh), Image.LANCZOS)
    return img.crop(((nw - tw) // 2, (nh - th) // 2,
                     (nw - tw) // 2 + tw, (nh - th) // 2 + th))


def get_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    # Prefer Impact-style condensed bold fonts that match packaging
    candidates = (
        [
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/Library/Fonts/Impact.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/truetype/msttcorefonts/Impact.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ] if bold else [
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
              max_w: int) -> list[str]:
    words = text.split()
    lines, cur = [], []
    for word in words:
        test = " ".join(cur + [word])
        if draw.textbbox((0, 0), test, font=font)[2] > max_w and cur:
            lines.append(" ".join(cur))
            cur = [word]
        else:
            cur.append(word)
    if cur:
        lines.append(" ".join(cur))
    return lines


def draw_text_block(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
                    color: tuple, max_w: int, cx: int, cy: int,
                    line_gap: int = 8) -> tuple[int, int]:
    """Draw centered text block. Returns (top_y, bottom_y)."""
    lines = wrap_text(draw, text, font, max_w)
    lh = font.size + line_gap
    total = len(lines) * lh
    y = cy - total // 2
    top = y
    for line in lines:
        bw = draw.textbbox((0, 0), line, font=font)[2]
        x = cx - bw // 2
        draw.text((x, y), line, font=font, fill=color)
        y += lh
    return top, y


def divider(draw: ImageDraw.Draw, y: int, color: tuple, thickness: int = 4):
    draw.rectangle([PAD, y, W - PAD, y + thickness], fill=color)


def progress_bar(draw: ImageDraw.Draw, current: int, total: int):
    """Dot-style progress bar at very bottom of slide."""
    dot_r = 10
    gap = 32
    n = total
    total_w = n * dot_r * 2 + (n - 1) * gap
    start_x = (W - total_w) // 2
    y = H - 28
    for i in range(n):
        cx = start_x + i * (dot_r * 2 + gap) + dot_r
        if i == current:
            draw.ellipse([cx - dot_r, y - dot_r, cx + dot_r, y + dot_r], fill=GOLD)
        else:
            draw.ellipse([cx - dot_r + 3, y - dot_r + 3,
                          cx + dot_r - 3, y + dot_r - 3], fill=(255, 255, 255, 80))
            draw.ellipse([cx - dot_r + 3, y - dot_r + 3,
                          cx + dot_r - 3, y + dot_r - 3],
                         outline=(184, 212, 94, 120), width=2)


# ─── SHARED: apply background photo with emerald overlay ─────────────────────
def apply_bg(canvas: Image.Image, bg_image: Image.Image | None,
             overlay_alpha: int = 185) -> Image.Image:
    if not bg_image:
        return canvas
    bg = resize_crop(bg_image, (W, H))
    overlay = Image.new("RGBA", (W, H), (26, 77, 46, overlay_alpha))
    result = Image.alpha_composite(bg.convert("RGBA"), overlay)
    return result.convert("RGB")


# ─── SLIDE 0: HOOK ───────────────────────────────────────────────────────────
def make_hook_slide(text: str, bg_image: Image.Image | None) -> Image.Image:
    canvas = Image.new("RGB", (W, H), EMERALD)
    canvas = apply_bg(canvas, bg_image, overlay_alpha=175)

    draw = ImageDraw.Draw(canvas)

    # ── Top: OPSIN™ PHONE WIPES header bar ──
    header_h = 110
    draw.rectangle([0, 0, W, header_h], fill=GOLD)
    f_brand = get_font(42)
    draw.text((W // 2, 38), "OPSIN™", font=f_brand, fill=EMERALD, anchor="mm")
    f_sub = get_font(28, bold=False)
    draw.text((W // 2, 80), "PHONE WIPES", font=f_sub, fill=EMERALD, anchor="mm")

    # ── Divider under header ──
    divider(draw, header_h + 10, GOLD, 3)

    # ── Hook text — massive, gold — vertically centered in remaining space ──
    content_top = header_h + 20
    content_bot = H - 130
    content_mid = content_top + (content_bot - content_top) // 2
    f_hook = get_font(118)
    _, bot = draw_text_block(draw, text.upper(), f_hook, GOLD,
                              W - PAD * 2, W // 2, content_mid, line_gap=14)

    # ── Divider above footer ──
    divider(draw, H - 140, GOLD, 3)

    # ── Bottom: tagline ──
    f_tag = get_font(44)
    draw.text((W // 2, H - 100), "YOUR PHONE IS GROSS™",
              font=f_tag, fill=WHITE, anchor="mm")

    # ── Progress bar ──
    progress_bar(draw, 0, 6)

    return canvas


# ─── SLIDES 1-3: BODY ────────────────────────────────────────────────────────
def make_body_slide(text: str, subtext: str, slide_num: int,
                    total_slides: int = 3,
                    bg_image: Image.Image | None = None) -> Image.Image:
    canvas = Image.new("RGB", (W, H), EMERALD)
    canvas = apply_bg(canvas, bg_image, overlay_alpha=190)
    draw = ImageDraw.Draw(canvas)

    # ── Top bar: brand + slide counter ──
    header_h = 110
    draw.rectangle([0, 0, W, header_h], fill=GOLD)
    f_brand = get_font(42)
    draw.text((PAD, 55), "OPSIN™", font=f_brand, fill=EMERALD, anchor="lm")
    f_counter = get_font(32, bold=False)
    draw.text((W - PAD, 55), f"{slide_num} / {total_slides}",
              font=f_counter, fill=EMERALD, anchor="rm")

    divider(draw, header_h + 10, GOLD, 3)

    # ── Main body text — vertically centered ──
    content_top = header_h + 20
    content_bot = H - 80
    content_mid = content_top + (content_bot - content_top) // 2
    f_main = get_font(100)
    _, bot = draw_text_block(draw, text.upper(), f_main, WHITE,
                              W - PAD * 2, W // 2, content_mid - 40, line_gap=12)

    # ── Subtext — gold ──
    if subtext and subtext.strip():
        f_sub = get_font(52, bold=False)
        draw_text_block(draw, subtext, f_sub, GOLD,
                        W - PAD * 2, W // 2, bot + 70)

    # ── Bottom rule + tagline ──
    divider(draw, H - 90, GOLD, 4)
    f_foot = get_font(30, bold=False)
    draw.text((W // 2, H - 65), "YOUR PHONE IS GROSS™",
              font=f_foot, fill=GOLD, anchor="mm")

    # ── Progress bar ──
    progress_bar(draw, slide_num, 6)

    return canvas


# ─── SLIDE CTA ───────────────────────────────────────────────────────────────
def make_cta_slide(text: str, bg_image: Image.Image | None = None) -> Image.Image:
    canvas = Image.new("RGB", (W, H), EMERALD)
    canvas = apply_bg(canvas, bg_image, overlay_alpha=200)
    draw = ImageDraw.Draw(canvas)

    # ── Top bar ──
    header_h = 110
    draw.rectangle([0, 0, W, header_h], fill=GOLD)
    f_brand = get_font(42)
    draw.text((W // 2, 55), "OPSIN™ PHONE WIPES", font=f_brand, fill=EMERALD, anchor="mm")

    divider(draw, header_h + 10, GOLD, 3)

    # ── CTA text — vertically centered in upper half ──
    f_cta = get_font(110)
    _, bot = draw_text_block(draw, text.upper(), f_cta, WHITE,
                              W - PAD * 2, W // 2, H // 2 - 100, line_gap=12)

    divider(draw, bot + 40, GOLD, 3)

    # ── Price badges ──
    badge_y = bot + 160
    badge_w, badge_h2 = 380, 140
    for i, (label, price) in enumerate([("LARGE BAG\n48 WIPES", "$12.99"),
                                         ("3-BAG BUNDLE\n144 WIPES", "$29.99")]):
        bx = W // 4 + i * (W // 2)
        draw.rounded_rectangle(
            [bx - badge_w // 2, badge_y - badge_h2 // 2,
             bx + badge_w // 2, badge_y + badge_h2 // 2],
            radius=16, fill=GOLD
        )
        f_lbl = get_font(28, bold=False)
        f_price = get_font(54)
        lines = label.split("\n")
        draw.text((bx, badge_y - 38), lines[0], font=f_lbl, fill=EMERALD, anchor="mm")
        if len(lines) > 1:
            draw.text((bx, badge_y - 10), lines[1], font=f_lbl, fill=EMERALD, anchor="mm")
        draw.text((bx, badge_y + 38), price, font=f_price, fill=EMERALD, anchor="mm")

    # ── TikTok Shop CTA ──
    f_shop = get_font(44)
    draw.text((W // 2, badge_y + 130), "🛍 TAP THE BAG TO ORDER",
              font=f_shop, fill=GOLD, anchor="mm")
    f_link = get_font(32, bold=False)
    draw.text((W // 2, badge_y + 190), "Fulfilled by Amazon · Ships fast",
              font=f_link, fill=WHITE, anchor="mm")

    # ── Bottom bar ──
    divider(draw, H - 90, GOLD, 4)
    f_foot = get_font(34)
    draw.text((W // 2, H - 65), "OPSIN™ · TIKTOK SHOP",
              font=f_foot, fill=GOLD, anchor="mm")

    # ── Progress bar (last slide = filled) ──
    progress_bar(draw, 5, 6)

    return canvas


# ─── BUILD ───────────────────────────────────────────────────────────────────
def build_slideshow_images(content: dict, images: list) -> list[Image.Image]:
    slides = []
    total = len(content["slides"])

    def img(i): return images[i] if i < len(images) else None

    slides.append(make_hook_slide(content["hook"], img(0)))
    for i, slide in enumerate(content["slides"]):
        slides.append(make_body_slide(
            slide["text"], slide.get("subtext", ""), i + 1, total, img(i + 1)
        ))
    slides.append(make_cta_slide(content["cta"], img(total + 1)))
    return slides


def build_slideshow_video(content: dict, images: list, output_path: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        frames = []
        slides = build_slideshow_images(content, images)
        durations = [SECONDS_PER_SLIDE] * (len(slides) - 1) + [SECONDS_PER_SLIDE + 1]
        for i, (slide, dur) in enumerate(zip(slides, durations)):
            path = os.path.join(tmpdir, f"slide_{i:03d}.jpg")
            slide.save(path, "JPEG", quality=95)
            frames.append((path, dur))

        concat_path = os.path.join(tmpdir, "concat.txt")
        with open(concat_path, "w") as f:
            for img_path, duration in frames:
                f.write(f"file '{img_path}'\n")
                f.write(f"duration {duration}\n")
            f.write(f"file '{frames[-1][0]}'\n")

        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_path,
            "-vf", f"scale={W}:{H}", "-c:v", "libx264",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-crf", "23", output_path
        ], check=True, capture_output=True)

    return output_path
