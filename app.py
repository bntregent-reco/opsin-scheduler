import os
import io
import zipfile
import tempfile
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv(override=True)

from config import NICHES, HOOK_FORMULAS, QUESTION_HOOKS, BRAND
from generator import generate_slideshow_content, generate_hook_variations
from slideshow import fetch_image, build_slideshow_images, build_slideshow_video

try:
    from poster import (
        get_auth_url, exchange_code_for_token, get_valid_token,
        load_token, post_photo_slideshow,
    )
    POSTER_AVAILABLE = True
    POSTER_ERR = ""
except Exception as e:
    POSTER_AVAILABLE = False
    POSTER_ERR = str(e)

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def save_env(key: str, value: str):
    """Persist a key=value pair to the .env file."""
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.readlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            updated = True
            break
    if not updated:
        lines.append(f"{key}={value}\n")
    with open(ENV_PATH, "w") as f:
        f.writelines(lines)


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="OPSIN Content Engine",
    page_icon="📱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Brand CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  [data-testid="stAppViewContainer"] { background: #0d0d0d; }
  [data-testid="stSidebar"] { background: #1A4D2E; }
  [data-testid="stSidebar"] * { color: #fff !important; }
  [data-testid="stSidebar"] input { color: #1A4D2E !important; background: #fff !important; }
  h1, h2, h3 { color: #B8D45E !important; }
  .stButton > button {
    background: #B8D45E; color: #1A4D2E;
    font-weight: 800; border: none; border-radius: 8px;
    padding: 0.6rem 1.4rem; font-size: 1rem;
  }
  .stButton > button:hover { background: #d4f070; }
  .metric-box {
    background: #1A4D2E; border-radius: 12px;
    padding: 1rem; text-align: center; margin: 0.3rem 0;
  }
  .caption-box {
    background: #1a1a1a; border-left: 4px solid #B8D45E;
    padding: 1rem 1.2rem; border-radius: 0 8px 8px 0;
    color: #fff; font-family: monospace; white-space: pre-wrap;
    font-size: 0.9rem;
  }
  .stSelectbox label, .stTextArea label, .stTextInput label { color: #B8D45E !important; }
  [data-testid="stMarkdownContainer"] p { color: #ccc; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 📱 OPSIN™")
    st.markdown("**YOUR PHONE IS GROSS™**")
    st.markdown("---")

    openai_key = st.text_input("OpenAI API Key", type="password",
                                value=os.getenv("OPENAI_API_KEY", ""),
                                help="Required for content generation")
    if openai_key and openai_key != os.getenv("OPENAI_API_KEY", ""):
        save_env("OPENAI_API_KEY", openai_key)
        os.environ["OPENAI_API_KEY"] = openai_key

    unsplash_key = st.text_input("Unsplash API Key", type="password",
                                  value=os.getenv("UNSPLASH_ACCESS_KEY", ""),
                                  help="Free at unsplash.com/developers")
    if unsplash_key and unsplash_key != os.getenv("UNSPLASH_ACCESS_KEY", ""):
        save_env("UNSPLASH_ACCESS_KEY", unsplash_key)
        os.environ["UNSPLASH_ACCESS_KEY"] = unsplash_key

    st.markdown("---")
    st.markdown("**TikTok Credentials**")

    tiktok_client_key = st.text_input("TikTok Client Key", type="password",
                                       value=os.getenv("TIKTOK_CLIENT_KEY", ""))
    if tiktok_client_key and tiktok_client_key != os.getenv("TIKTOK_CLIENT_KEY", ""):
        save_env("TIKTOK_CLIENT_KEY", tiktok_client_key)
        os.environ["TIKTOK_CLIENT_KEY"] = tiktok_client_key

    tiktok_client_secret = st.text_input("TikTok Client Secret", type="password",
                                          value=os.getenv("TIKTOK_CLIENT_SECRET", ""))
    if tiktok_client_secret and tiktok_client_secret != os.getenv("TIKTOK_CLIENT_SECRET", ""):
        save_env("TIKTOK_CLIENT_SECRET", tiktok_client_secret)
        os.environ["TIKTOK_CLIENT_SECRET"] = tiktok_client_secret

    st.markdown("---")

    if st.button("💾 Save All Keys", use_container_width=True):
        if openai_key:
            save_env("OPENAI_API_KEY", openai_key)
        if unsplash_key:
            save_env("UNSPLASH_ACCESS_KEY", unsplash_key)
        if tiktok_client_key:
            save_env("TIKTOK_CLIENT_KEY", tiktok_client_key)
        if tiktok_client_secret:
            save_env("TIKTOK_CLIENT_SECRET", tiktok_client_secret)
        st.success("Saved!")

    st.markdown("---")
    export_video = st.checkbox("Export as MP4 video", value=False,
                                help="Requires ffmpeg installed")

    st.markdown("---")
    st.markdown("**Content Rules**")
    st.markdown("✅ Screen-safe  \n✅ Alcohol-free  \n✅ Plant-based  \n✅ Daily Ritual")
    st.markdown("❌ No disinfectant claims  \n❌ No antimicrobial  \n❌ No 'kills bacteria'")

# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# OPSIN Content Engine")
st.markdown("Generate TikTok slideshows in Opsin's brand voice. One click.")
st.markdown("---")

tab_create, tab_schedule = st.tabs(["⚡ Create", "📅 Schedule & Post"])

# ── CREATE TAB ────────────────────────────────────────────────────────────────
with tab_create:
    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("### 1. Pick Your Angle")
        niche = st.selectbox("Content Niche", list(NICHES.keys()), index=0)
        st.caption(NICHES[niche])

        st.markdown("### 2. Choose Your Hook")
        hook_mode = st.radio("Hook source",
                              ["Question hook", "Statement hook", "Generate AI hooks", "Write my own"],
                              horizontal=True)

        selected_hook = ""
        if hook_mode == "Question hook":
            selected_hook = st.selectbox("Question hook", QUESTION_HOOKS)
            st.caption("Question hooks create instant pattern interrupt — viewer must answer before swiping.")
        elif hook_mode == "Statement hook":
            selected_hook = st.selectbox("Statement hook", HOOK_FORMULAS)
        elif hook_mode == "Generate AI hooks":
            if st.button("Generate 5 hooks for this niche"):
                if not openai_key:
                    st.error("Add your OpenAI API key in the sidebar.")
                else:
                    with st.spinner("Generating hooks..."):
                        os.environ["OPENAI_API_KEY"] = openai_key
                        hooks = generate_hook_variations(niche, 5)
                        st.session_state["ai_hooks"] = hooks
            if "ai_hooks" in st.session_state:
                selected_hook = st.selectbox("Pick a hook", st.session_state["ai_hooks"])
        else:
            selected_hook = st.text_input("Your custom hook (max 12 words)")

        st.markdown("### 3. Generate")
        generate_btn = st.button("⚡ Generate Slideshow", use_container_width=True)

    with col2:
        st.markdown("### Preview will appear here")

    if generate_btn:
        if not openai_key:
            st.error("Add your OpenAI API key in the sidebar.")
            st.stop()
        if not selected_hook:
            st.error("Select or write a hook first.")
            st.stop()

        os.environ["OPENAI_API_KEY"] = openai_key

        with st.spinner("Writing your slideshow..."):
            content = generate_slideshow_content(niche, selected_hook)
            st.session_state["content"] = content

        with st.spinner("Fetching images from Unsplash..."):
            from slideshow import SLIDE_IMAGE_QUERIES
            import random
            images = []
            for slot_queries in SLIDE_IMAGE_QUERIES:
                if unsplash_key:
                    q = random.choice(slot_queries)
                    img = fetch_image(q, unsplash_key)
                    images.append(img)
                else:
                    images.append(None)
            st.session_state["images"] = images

        with st.spinner("Rendering slides..."):
            slides = build_slideshow_images(content, images)
            st.session_state["slides"] = slides

    if "slides" in st.session_state:
        content = st.session_state["content"]
        slides  = st.session_state["slides"]
        images  = st.session_state.get("images", [])

        st.markdown("---")
        moat_labels = {
            "alcohol_damage": "🧪 Alcohol Damage",
            "plant_based": "🌿 Plant-Based Formula",
            "biodegradable": "♻️ Biodegradable Wipe",
        }
        moat = moat_labels.get(content.get("moat_angle", ""), "")
        st.markdown(f"## Generated Slideshow &nbsp; `{moat}`", unsafe_allow_html=True)

        slide_labels = ["HOOK"] + [f"SLIDE {i+1}" for i in range(len(content["slides"]))] + ["CTA"]
        cols = st.columns(len(slides))
        for i, (col, slide, label) in enumerate(zip(cols, slides, slide_labels)):
            with col:
                preview = slide.copy()
                preview.thumbnail((300, 600))
                st.image(preview, caption=label, use_container_width=True)

        st.markdown("---")
        left, right = st.columns([2, 1])

        with left:
            st.markdown("### Caption")
            hashtag_str = " ".join(f"#{h}" for h in content.get("hashtags", []))
            full_caption = content.get("caption", "") + "\n\n" + hashtag_str
            st.markdown(f'<div class="caption-box">{full_caption}</div>', unsafe_allow_html=True)
            st.button("📋 Copy Caption", on_click=lambda: None)

        with right:
            st.markdown("### Slide Content")
            st.markdown(f'<div class="metric-box"><b style="color:#B8D45E">HOOK</b><br><span style="color:#fff;font-size:0.9rem">{content["hook"]}</span></div>', unsafe_allow_html=True)
            for i, s in enumerate(content["slides"]):
                st.markdown(f'<div class="metric-box"><b style="color:#B8D45E">SLIDE {i+1}</b><br><span style="color:#fff;font-size:0.9rem">{s["text"]}</span></div>', unsafe_allow_html=True)
            st.markdown(f'<div class="metric-box"><b style="color:#B8D45E">CTA</b><br><span style="color:#fff;font-size:0.9rem">{content["cta"]}</span></div>', unsafe_allow_html=True)

        st.markdown("---")
        exp_col1, exp_col2, exp_col3 = st.columns(3)

        with exp_col1:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for i, slide in enumerate(slides):
                    img_buf = io.BytesIO()
                    slide.save(img_buf, "JPEG", quality=95)
                    zf.writestr(f"opsin_slide_{i:02d}.jpg", img_buf.getvalue())
                zf.writestr("caption.txt", full_caption)
            zip_buffer.seek(0)
            st.download_button("⬇️ Download All Slides (ZIP)",
                               data=zip_buffer, file_name="opsin_slideshow.zip",
                               mime="application/zip", use_container_width=True)

        with exp_col2:
            st.download_button("⬇️ Download Caption",
                               data=full_caption, file_name="opsin_caption.txt",
                               mime="text/plain", use_container_width=True)

        with exp_col3:
            if export_video:
                if st.button("🎬 Export MP4 Video", use_container_width=True):
                    with st.spinner("Stitching video with ffmpeg..."):
                        try:
                            out_path = tempfile.mktemp(suffix=".mp4")
                            build_slideshow_video(content, images, out_path)
                            with open(out_path, "rb") as f:
                                st.download_button("⬇️ Download MP4",
                                                   data=f.read(),
                                                   file_name="opsin_slideshow.mp4",
                                                   mime="video/mp4")
                        except Exception as e:
                            st.error(f"ffmpeg error: {e}")
            else:
                st.info("Enable 'Export as MP4' in sidebar for video export.")

        st.markdown("---")
        if st.button("🔄 Regenerate with same settings"):
            st.rerun()


# ── SCHEDULE TAB ──────────────────────────────────────────────────────────────
with tab_schedule:
    st.markdown("## TikTok Auto-Poster")

    if not POSTER_AVAILABLE:
        st.error(f"Poster module error: {POSTER_ERR}")
    else:
        REDIRECT_URI = "https://getopsin.com/callback"
        has_token = get_valid_token(tiktok_client_key, tiktok_client_secret) if (tiktok_client_key and tiktok_client_secret) else None

        if has_token:
            st.success("✅ TikTok account connected — auto-posting is active")
        else:
            st.warning("⚠️ TikTok not connected. Connect below to enable auto-posting.")

        st.markdown("---")
        st.markdown("### Connect TikTok Account")

        if not tiktok_client_key or not tiktok_client_secret:
            st.info("Add your TikTok Client Key and Secret in the sidebar first.")
        else:
            auth_url = get_auth_url(tiktok_client_key, REDIRECT_URI)
            st.markdown(f"**Step 1** — [Click here to authorize on TikTok ↗]({auth_url})")
            st.caption("After approving, you'll land on a 404 page — copy the ENTIRE URL from the address bar and paste it below.")

            st.markdown("**Step 2** — Paste the full URL from your browser:")
            code_input = st.text_input("Full URL (e.g. https://getopsin.com/callback?code=...)", key="tt_code")
            if st.button("🔗 Connect TikTok Account", key="connect_tt"):
                raw = code_input.strip()
                if "?code=" in raw:
                    raw = raw.split("?code=")[1].split("&")[0]
                if raw:
                    with st.spinner("Connecting..."):
                        result = exchange_code_for_token(
                            raw, tiktok_client_key, tiktok_client_secret, REDIRECT_URI
                        )
                    if result:
                        st.success("✅ Connected! Your @Opsin account is now linked.")
                        st.rerun()
                    else:
                        st.error("Connection failed. The code expires in 10 minutes — try the auth link again immediately.")
                else:
                    st.error("Paste the full URL first.")

        st.markdown("---")
        st.markdown("### Post Schedule")
        st.markdown("""
| Time | Posts |
|------|-------|
| 6:00 AM ET | ✅ Auto |
| 12:00 PM ET | ✅ Auto |
| 7:00 PM ET | ✅ Auto |
""")
        st.info("To start auto-posting: open a new Terminal window and run:\n\n`python3 /Users/Benoitregent/Desktop/RECO/opsin-slideshow/scheduler.py`")

        if "slides" in st.session_state:
            st.markdown("---")
            st.markdown("### Post Current Slideshow Now")
            if has_token:
                if st.button("📤 Post to TikTok Now", use_container_width=True):
                    _content = st.session_state["content"]
                    _slides  = st.session_state["slides"]
                    _hashtags = " ".join(f"#{h}" for h in _content.get("hashtags", []))
                    _caption = _content.get("caption", "") + "\n\n" + _hashtags
                    with st.spinner("Uploading to TikTok..."):
                        result = post_photo_slideshow(has_token, _slides, _caption)
                    if result.get("success"):
                        st.success(f"✅ Posted! publish_id: {result.get('publish_id')}")
                    else:
                        st.error(f"Failed: {result}")
            else:
                st.info("Connect your TikTok account above to post.")
