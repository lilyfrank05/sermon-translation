"""Fetch Bible verses from BibleGateway."""

import re
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from .config import BIBLEGATEWAY_URL, DEFAULT_BIBLE_VERSION

# Regex pattern for Bible verse references
# Matches patterns like: John 3:16, 1 Corinthians 13:4-7, Psalm 23:1-6, Romans 8:28
VERSE_PATTERN = re.compile(
    r"\b("
    # Books starting with a number
    r"(?:[123]\s*)?"
    # Book names (common ones)
    r"(?:Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    r"Samuel|Kings|Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|"
    r"Ecclesiastes|Song\s+of\s+Solomon|Isaiah|Jeremiah|Lamentations|Ezekiel|"
    r"Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|"
    r"Haggai|Zechariah|Malachi|Matthew|Mark|Luke|John|Acts|Romans|"
    r"Corinthians|Galatians|Ephesians|Philippians|Colossians|Thessalonians|"
    r"Timothy|Titus|Philemon|Hebrews|James|Peter|Jude|Revelation)"
    # Chapter and verse
    r"\s+\d+:\d+(?:-\d+)?(?:,\s*\d+(?:-\d+)?)*"
    r")\b",
    re.IGNORECASE,
)


class BibleFetcher:
    """Fetches Bible verses from BibleGateway."""

    def __init__(self, version: str = DEFAULT_BIBLE_VERSION):
        self.version = version
        self._cache: dict[str, str] = {}

    def detect_references(self, text: str) -> list[str]:
        """
        Detect Bible verse references in the given text.

        Args:
            text: Text to search for verse references

        Returns:
            List of unique verse references found
        """
        matches = VERSE_PATTERN.findall(text)
        # Normalize and deduplicate
        seen = set()
        result = []
        for match in matches:
            normalized = " ".join(match.split())
            if normalized.lower() not in seen:
                seen.add(normalized.lower())
                result.append(normalized)
        return result

    def fetch_verse(self, reference: str) -> str | None:
        """
        Fetch a Bible verse from BibleGateway.

        Args:
            reference: Bible verse reference (e.g., "John 3:16")

        Returns:
            The verse text in Chinese, or None if not found
        """
        if reference in self._cache:
            return self._cache[reference]

        url = f"{BIBLEGATEWAY_URL}?search={quote(reference)}&version={self.version}"

        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as e:
            print(f"Warning: Failed to fetch {reference}: {e}")
            return None

        # Parse the HTML to extract verse text
        soup = BeautifulSoup(response.text, "html.parser")

        # Find the passage text container
        passage_div = soup.find("div", class_="passage-text")
        if not passage_div:
            print(f"Warning: Could not find passage text for {reference}")
            return None

        # Extract text from verse spans, excluding verse numbers
        verses = []
        for verse_span in passage_div.find_all("span", class_="text"):
            # Get text content, excluding verse number spans
            text_parts = []
            for child in verse_span.children:
                if hasattr(child, "get") and "versenum" in child.get("class", []):
                    continue
                if hasattr(child, "get") and "chapternum" in child.get("class", []):
                    continue
                if isinstance(child, str):
                    text_parts.append(child)
                elif hasattr(child, "get_text"):
                    text_parts.append(child.get_text())

            verse_text = "".join(text_parts).strip()
            if verse_text:
                verses.append(verse_text)

        if not verses:
            print(f"Warning: No verse text found for {reference}")
            return None

        result = " ".join(verses)
        self._cache[reference] = result
        return result

    def fetch_all(self, text: str) -> dict[str, str]:
        """
        Detect and fetch all Bible verses referenced in the text.

        Args:
            text: Text containing Bible verse references

        Returns:
            Dictionary mapping references to their Chinese translations
        """
        references = self.detect_references(text)
        result = {}

        for ref in references:
            verse_text = self.fetch_verse(ref)
            if verse_text:
                result[ref] = verse_text

        return result

    def format_verse_table(self, verses: dict[str, str]) -> str:
        """
        Format verses as a lookup table for the translation prompt.

        Args:
            verses: Dictionary mapping references to Chinese text

        Returns:
            Formatted string for inclusion in the prompt
        """
        if not verses:
            return "[No Bible verse references detected]"

        lines = ["[BIBLE VERSE REFERENCE TABLE]"]
        for ref, text in verses.items():
            lines.append(f"- {ref}: {text}")

        return "\n".join(lines)
