from __future__ import annotations
import json
import re
import os
import random
from openai import OpenAI
from config import BRAND, NICHES, HOOK_FORMULAS, PRODUCT_MOATS


def generate_slideshow_content(niche: str, hook_formula: str, custom_hook: str = "") -> dict:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    hook = custom_hook.strip() if custom_hook.strip() else hook_formula
    niche_context = NICHES.get(niche, niche)
    moat = random.choice(PRODUCT_MOATS)

    system_prompt = f"""You are the content engine for OPSIN Phone Wipes.

BRAND VOICE: {BRAND['voice']}

CORE TRUTH: "YOUR PHONE IS GROSS™" — phones have 25,127 bacteria/sq inch, touched 1,500x/day, never cleaned.

PRODUCT: OPSIN Phone Wipes — alcohol-free, plant-based, biodegradable, Screen Safe Technology™.
SKUs: {BRAND['skus']['single']['name']} ({BRAND['skus']['single']['price']}) | {BRAND['skus']['bundle']['name']} ({BRAND['skus']['bundle']['price']})

NEVER SAY: {', '.join(BRAND['claims_forbidden'])}
YOU CAN SAY: {', '.join(BRAND['claims_allowed'])}

OUTPUT FORMAT: Return only valid JSON, no markdown, no explanation."""

    is_question = hook.strip().endswith("?")
    slide1_instruction = (
        "Slide 1: ANSWER the hook question immediately — short, shocking reveal. E.g. 'YOUR PHONE.' Then hit them with the reality."
        if is_question else
        "Slide 1: Niche-specific disgust or problem. Make them feel it."
    )

    user_prompt = f"""Generate a TikTok slideshow for OPSIN. Follow the EXACT 4-slide structure below.

NICHE: {niche}
NICHE CONTEXT: {niche_context}
HOOK: {hook}
HOOK TYPE: {"QUESTION — slide 1 must deliver the answer as a gut-punch reveal" if is_question else "STATEMENT — slide 1 deepens the problem"}

MANDATORY SLIDE STRUCTURE:
- {slide1_instruction}
- Slide 2: Deepen the problem. Stack the reality.
- Slide 3: PRODUCT MOAT — use this exact angle: "{moat['angle']}"
  Headline to adapt: "{moat['headline']}"
  Context: "{moat['detail']}"
  Make it punchy and on-brand. This is where OPSIN wins vs every competitor.
- Slide 4: PRICE ANCHOR — always "27¢ per clean" framing.
  Make it feel cheap. Compare to something trivial (gum, coffee, a text message).

Return this exact JSON:
{{
  "hook": "opening hook (max 12 words, punchy)",
  "slides": [
    {{"text": "slide 1 text (max 12 words)", "subtext": "supporting line (max 8 words, or empty)"}},
    {{"text": "slide 2 text (max 12 words)", "subtext": ""}},
    {{"text": "slide 3 moat text (max 12 words)", "subtext": "one sharp supporting line"}},
    {{"text": "slide 4 price anchor (max 10 words)", "subtext": "comparison line — e.g. less than a stick of gum"}}
  ],
  "cta": "max 7 words. TikTok Shop close. No URL. E.g. 'Your phone is waiting. Tap the bag.'",
  "caption": "2-3 sentences, Opsin voice, human not corporate.",
  "hashtags": ["phonehygiene", "yourphoneisgross", "opsin", "screensafe", "phonewipes"],
  "image_queries": ["hook image", "slide 1 image", "slide 2 image", "slide 3 image", "slide 4 image", "cta image"]
}}

Rules:
- Blunt. State. Never suggest. Short sentences.
- Slide 3 must clearly differentiate OPSIN from alcohol-based competitors.
- Slide 4 must make $12.99 feel trivially cheap.
- CTA drives to TikTok Shop. Never mention a URL."""

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1200,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    data = json.loads(raw)
    data["moat_angle"] = moat["angle"]
    return data


def generate_hook_variations(niche: str, count: int = 5) -> list[str]:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    niche_context = NICHES.get(niche, niche)

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=512,
        messages=[{
            "role": "user",
            "content": f"""Generate {count} TikTok hooks for OPSIN Phone Wipes targeting the '{niche}' niche.

Niche context: {niche_context}
Brand voice: {BRAND['voice']}
Core truth: Your phone is gross. 25,127 bacteria/sq inch. Never cleaned.
NEVER use: {', '.join(BRAND['claims_forbidden'])}

Return only a JSON array of {count} hook strings. No other text.
Each hook: max 12 words. Punchy. Creates discomfort or curiosity."""
        }],
    )

    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)
