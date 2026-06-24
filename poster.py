from __future__ import annotations
import os
import io
import json
import time
import requests

TIKTOK_AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
TIKTOK_POST_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/content/init/"
TIKTOK_POST_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"

TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".tiktok_token.json")


# ── Token storage ─────────────────────────────────────────────────────────────

def save_token(data: dict):
    data["saved_at"] = time.time()
    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)


def load_token() -> dict | None:
    if not os.path.exists(TOKEN_FILE):
        return None
    with open(TOKEN_FILE) as f:
        return json.load(f)


def token_is_valid(token: dict) -> bool:
    if not token:
        return False
    age = time.time() - token.get("saved_at", 0)
    # expires_in is typically 86400 (24h), refresh at 23h
    return age < (token.get("expires_in", 86400) - 3600)


def refresh_access_token(token: dict, client_key: str, client_secret: str) -> dict | None:
    resp = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": client_key,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": token["refresh_token"],
    })
    if resp.status_code == 200:
        body = resp.json()
        data = body.get("data") or body  # sandbox returns flat, production returns nested
        if data.get("access_token"):
            save_token(data)
            return data
    return None


def get_valid_token(client_key: str, client_secret: str) -> str | None:
    token = load_token()
    if not token:
        return None
    if token_is_valid(token):
        return token["access_token"]
    refreshed = refresh_access_token(token, client_key, client_secret)
    return refreshed["access_token"] if refreshed else None


# ── OAuth URL ─────────────────────────────────────────────────────────────────

def get_auth_url(client_key: str, redirect_uri: str) -> str:
    import urllib.parse
    params = {
        "client_key": client_key,
        "scope": "user.info.basic,video.upload",
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "state": "opsin_scheduler",
    }
    return TIKTOK_AUTH_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_token(code: str, client_key: str, client_secret: str,
                             redirect_uri: str) -> dict | None:
    resp = requests.post(TIKTOK_TOKEN_URL, data={
        "client_key": client_key,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        if data.get("access_token"):
            save_token(data)
            return data
    return None


# ── Photo post ────────────────────────────────────────────────────────────────

def post_photo_slideshow(
    access_token: str,
    images: list,          # list of PIL Images
    caption: str,
    privacy: str = "PUBLIC_TO_EVERYONE",
) -> dict:
    """
    Post a photo slideshow to TikTok using the Content Posting API.
    Returns the API response dict.
    """
    n = len(images)

    # Step 1: Initialize the post
    clean_title = caption.replace("\n", " ").strip()[:2200]
    init_payload = {
        "media_type": "PHOTO",
        "post_info": {
            "title": clean_title,
            "privacy_level": "SELF_ONLY",
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "photo_images": n,
            "photo_cover_index": 0,
        },
    }

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
    }

    init_resp = requests.post(TIKTOK_POST_INIT_URL, json=init_payload, headers=headers)
    print("=== TIKTOK INIT DEBUG ===")
    print("Payload:", json.dumps(init_payload, indent=2))
    print("Status:", init_resp.status_code)
    print("Response:", init_resp.text)
    print("=========================")
    init_data = init_resp.json()

    if init_resp.status_code != 200 or init_data.get("error", {}).get("code", "ok") != "ok":
        return {"success": False, "error": init_data, "step": "init"}

    data = init_data.get("data", {})
    publish_id = data.get("publish_id")
    upload_urls = data.get("upload_urls", [])

    if not upload_urls:
        return {"success": False, "error": "No upload URLs returned", "step": "init"}

    # Step 2: Upload each image to its signed URL
    for i, (img, url) in enumerate(zip(images, upload_urls)):
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=95)
        buf.seek(0)
        upload_resp = requests.put(
            url,
            data=buf.read(),
            headers={"Content-Type": "image/jpeg"},
        )
        if upload_resp.status_code not in (200, 204):
            return {"success": False, "error": f"Upload failed for image {i}", "step": "upload"}

    # Step 3: Poll for publish status
    for _ in range(10):
        time.sleep(3)
        status_resp = requests.post(
            TIKTOK_POST_STATUS_URL,
            json={"publish_id": publish_id},
            headers=headers,
        )
        status_data = status_resp.json()
        status = status_data.get("data", {}).get("status", "")
        if status == "PUBLISH_COMPLETE":
            return {"success": True, "publish_id": publish_id, "status": status}
        if status in ("FAILED", "PUBLISH_FAILED"):
            return {"success": False, "publish_id": publish_id, "status": status, "step": "publish"}

    return {"success": True, "publish_id": publish_id, "status": "PROCESSING", "note": "Still processing"}
