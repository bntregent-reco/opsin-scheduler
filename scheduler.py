from __future__ import annotations
"""
Opsin TikTok Scheduler — posts 3x/day at 6am, 12pm, 7pm.
Run standalone: python3 scheduler.py
"""
import os
import random
import logging
from datetime import datetime

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("opsin_scheduler")

# Post times (24h, local machine time)
POST_HOURS = [6, 12, 19]


def run_post():
    """Generate and post one slideshow to TikTok."""
    from config import NICHES, QUESTION_HOOKS
    from generator import generate_slideshow_content
    from slideshow import fetch_image, build_slideshow_images, SLIDE_IMAGE_QUERIES
    from poster import get_valid_token, post_photo_slideshow

    client_key    = os.environ.get("TIKTOK_CLIENT_KEY", "")
    client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    openai_key    = os.environ.get("OPENAI_API_KEY", "")
    unsplash_key  = os.environ.get("UNSPLASH_ACCESS_KEY", "")

    if not all([client_key, client_secret, openai_key]):
        log.error("Missing required env vars. Check TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, OPENAI_API_KEY.")
        return

    os.environ["OPENAI_API_KEY"] = openai_key

    access_token = get_valid_token(client_key, client_secret)
    if not access_token:
        log.error("No valid TikTok token. Open the Streamlit app and connect your TikTok account.")
        return

    # Pick random niche + question hook
    niche = random.choice(list(NICHES.keys()))
    hook  = random.choice(QUESTION_HOOKS)
    log.info(f"Generating: niche='{niche}' hook='{hook[:50]}...'")

    content = generate_slideshow_content(niche, hook)
    log.info(f"Content generated. Moat: {content.get('moat_angle')}")

    # Fetch images
    images = []
    for slot_queries in SLIDE_IMAGE_QUERIES:
        if unsplash_key:
            q = random.choice(slot_queries)
            from slideshow import fetch_image
            img = fetch_image(q, unsplash_key)
            images.append(img)
        else:
            images.append(None)

    slides = build_slideshow_images(content, images)
    log.info(f"Rendered {len(slides)} slides.")

    # Build caption
    hashtags = " ".join(f"#{h}" for h in content.get("hashtags", []))
    caption = content.get("caption", "") + "\n\n" + hashtags

    result = post_photo_slideshow(access_token, slides, caption)

    if result.get("success"):
        log.info(f"Posted! publish_id={result.get('publish_id')} status={result.get('status')}")
    else:
        log.error(f"Post failed: {result}")


def start():
    scheduler = BlockingScheduler(timezone="America/New_York")

    for hour in POST_HOURS:
        scheduler.add_job(run_post, "cron", hour=hour, minute=0, id=f"post_{hour}h")
        log.info(f"Scheduled post at {hour:02d}:00 ET")

    log.info("Scheduler running. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    start()
