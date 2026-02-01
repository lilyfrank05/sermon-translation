"""Configuration constants and settings loaded from .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env file from project root
# __file__ = src/sermon_translator/config.py
# .parent = src/sermon_translator
# .parent.parent = src
# .parent.parent.parent = project root
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path, override=True)


def _get_float(key: str, default: float) -> float:
    """Get a float value from environment."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_int(key: str, default: int) -> int:
    """Get an int value from environment."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


# OpenRouter settings
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "openai/gpt-4o")
TRANSLATION_TEMPERATURE = _get_float("TRANSLATION_TEMPERATURE", 0.3)
REVIEW_TEMPERATURE = _get_float("REVIEW_TEMPERATURE", 0.2)

# Bible settings
DEFAULT_BIBLE_VERSION = os.environ.get("DEFAULT_BIBLE_VERSION", "CCB")
BIBLEGATEWAY_URL = os.environ.get("BIBLEGATEWAY_URL", "https://www.biblegateway.com/passage/")

# Font settings
LATIN_FONT = os.environ.get("LATIN_FONT", "Microsoft YaHei")
EAST_ASIAN_FONT = os.environ.get("EAST_ASIAN_FONT", "Microsoft YaHei")
FONT_SIZE_PT = _get_int("FONT_SIZE_PT", 14)

# Translation chunking
MAX_TOKENS_PER_CHUNK = _get_int("MAX_TOKENS_PER_CHUNK", 2000)
MAX_PARAGRAPHS_PER_CHUNK = _get_int("MAX_PARAGRAPHS_PER_CHUNK", 10)

# Review settings
MAX_REVIEW_ITERATIONS = _get_int("MAX_REVIEW_ITERATIONS", 2)

# Translation rules (shared between translation and review)
TRANSLATION_RULES = """
1. When "he/He/Him/His" refers to God, translate to 祂
2. Translate "God" to 上帝, not 神 (unless it's a direct Bible quote from that specific Chinese version)
3. For names:
   - Biblical names SHOULD be translated (e.g., "Peter" → "彼得", "Paul" → "保罗", "Moses" → "摩西")
   - Non-biblical names (authors, modern people) should be kept in English
4. Do not paraphrase - preserve original paragraph structure and meaning
5. Use natural, native Chinese expressions
6. For Bible verse quotations, use the EXACT Chinese text provided in the reference table below (if provided)
"""

# Translation system prompt
TRANSLATION_SYSTEM_PROMPT = """You are translating Christian sermon notes from English to Mandarin Chinese (Simplified).

Rules:
""" + TRANSLATION_RULES + """
{verse_table}

IMPORTANT:
- Maintain the same number of paragraphs as the input
- Each paragraph in your output should correspond to the same paragraph in the input
- Use the markers [P1], [P2], etc. to indicate paragraph boundaries
- Only output the translated text with paragraph markers, no explanations"""

# Review system prompt
REVIEW_SYSTEM_PROMPT = """You are reviewing a Chinese translation of English sermon notes.

The translation MUST follow these rules:
""" + TRANSLATION_RULES + """
Check for:
1. Accuracy: Does the translation preserve the original meaning?
2. Naturalness: Does it sound like native Mandarin Chinese?
3. Consistency: Are theological terms translated consistently?
4. Pronouns: Is 祂 used for God's pronouns? Is 上帝 used (not 神)?
5. Names: Are biblical names translated to Chinese? Are non-biblical names kept in English?

IMPORTANT: Do NOT review or modify direct Bible quotations. Bible verses from the reference table below are from an authoritative source (BibleGateway) and must be kept exactly as provided. Skip any text that matches a Bible verse reference.

Original English:
{original}

Translated Chinese:
{translated}

Bible Verse References (exempt from review - do not modify these):
{verse_table}

If the translation is perfect, respond with exactly: APPROVED

If there are issues, respond in this JSON format:
{{
    "issues": [
        {{
            "paragraph": 1,
            "original_text": "problematic text",
            "issue_type": "accuracy|naturalness|consistency|pronoun|name",
            "suggestion": "corrected text"
        }}
    ],
    "corrected_translation": "full corrected translation with [P1], [P2] markers"
}}"""
