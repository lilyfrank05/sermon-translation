"""OpenRouter-based translation logic."""

from openai import OpenAI

from .config import (
    DEFAULT_MODEL,
    MAX_PARAGRAPHS_PER_CHUNK,
    MAX_TOKENS_PER_CHUNK,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_TEMPERATURE,
)
from .docx_handler import Paragraph


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a text string.

    Uses a rough heuristic: ~1.5 tokens per Chinese character, ~0.25 tokens per English character.
    This is conservative to avoid hitting limits.
    """
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.5 + other_chars * 0.25) + 10  # +10 for safety margin


class Translator:
    """Translates text using OpenRouter API."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = OpenAI(
            api_key=api_key or OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )
        self.model = model or DEFAULT_MODEL

    def translate_paragraphs(
        self,
        paragraphs: list[Paragraph],
        verse_table: str = "",
        progress_callback=None,
    ) -> list[str]:
        """
        Translate paragraphs from English to Chinese.

        Args:
            paragraphs: List of paragraphs to translate
            verse_table: Formatted Bible verse reference table
            progress_callback: Optional callback for progress updates

        Returns:
            List of translated text for each paragraph
        """
        # Split into chunks
        chunks = self._chunk_paragraphs(paragraphs)
        all_translations = []

        for i, chunk in enumerate(chunks):
            if progress_callback:
                progress_callback(i + 1, len(chunks))

            translations = self._translate_chunk(chunk, verse_table)
            all_translations.extend(translations)

        return all_translations

    def _chunk_paragraphs(
        self,
        paragraphs: list[Paragraph],
    ) -> list[list[tuple[int, Paragraph]]]:
        """
        Split paragraphs into chunks for translation.

        Uses both paragraph count and token limits to determine chunk boundaries.
        Returns list of chunks, where each chunk is a list of (index, paragraph) tuples.
        """
        chunks = []
        current_chunk = []
        current_tokens = 0

        for i, para in enumerate(paragraphs):
            para_tokens = estimate_tokens(para.text)

            # Check if adding this paragraph would exceed limits
            would_exceed_paragraphs = len(current_chunk) >= MAX_PARAGRAPHS_PER_CHUNK
            would_exceed_tokens = (current_tokens + para_tokens) > MAX_TOKENS_PER_CHUNK and current_chunk

            if would_exceed_paragraphs or would_exceed_tokens:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0

            current_chunk.append((i, para))
            current_tokens += para_tokens

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _translate_chunk(
        self,
        chunk: list[tuple[int, Paragraph]],
        verse_table: str,
        retry_count: int = 0,
    ) -> list[str]:
        """
        Translate a chunk of paragraphs.

        Args:
            chunk: List of (index, paragraph) tuples
            verse_table: Formatted Bible verse reference table
            retry_count: Current retry attempt (for logging)

        Returns:
            List of translated text in order
        """
        # Build the input text with paragraph markers
        input_lines = []
        for idx, para in chunk:
            text = para.text.strip()
            marker = f"[P{idx + 1}]"
            if text:
                input_lines.append(f"{marker} {text}")
            else:
                input_lines.append(marker)

        input_text = "\n".join(input_lines)

        # Build the system prompt with verse table
        system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
            verse_table=verse_table if verse_table else "[No Bible verse references]"
        )

        # Call OpenRouter API
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=TRANSLATION_TEMPERATURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
        )

        translated_text = response.choices[0].message.content or ""

        # Parse the response to extract translations for each paragraph
        results = self._parse_response(translated_text, chunk)

        # Check for untranslated paragraphs (empty results for non-empty inputs)
        missing_indices = []
        for i, (idx, para) in enumerate(chunk):
            if para.text.strip() and not results[i]:
                missing_indices.append(i)

        # Retry missing paragraphs individually if any were missed
        if missing_indices and retry_count < 2:
            for i in missing_indices:
                idx, para = chunk[i]
                # Translate single paragraph
                single_result = self._translate_single_paragraph(idx, para, verse_table)
                if single_result:
                    results[i] = single_result

        return results

    def _translate_single_paragraph(
        self,
        idx: int,
        para: Paragraph,
        verse_table: str,
    ) -> str:
        """
        Translate a single paragraph (used for retry).

        Args:
            idx: Original paragraph index
            para: Paragraph to translate
            verse_table: Formatted Bible verse reference table

        Returns:
            Translated text
        """
        text = para.text.strip()
        if not text:
            return ""

        marker = f"[P{idx + 1}]"
        input_text = f"{marker} {text}"

        system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
            verse_table=verse_table if verse_table else "[No Bible verse references]"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            temperature=TRANSLATION_TEMPERATURE,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
        )

        translated_text = response.choices[0].message.content or ""

        # Parse single paragraph response
        import re
        pattern = rf"\[P{idx + 1}\]\s*(.*?)$"
        match = re.search(pattern, translated_text, re.DOTALL)

        if match:
            return match.group(1).strip()

        # Fallback: return the whole response if no marker found
        # (model might just output the translation directly)
        return translated_text.strip()

    def _parse_response(
        self,
        response: str,
        chunk: list[tuple[int, Paragraph]],
    ) -> list[str]:
        """
        Parse the translated response to extract text for each paragraph.

        Args:
            response: The model's response with [P1], [P2], etc. markers
            chunk: The original chunk to match paragraph count

        Returns:
            List of translated text in order
        """
        import re

        result = []

        for idx, _ in chunk:
            marker = f"[P{idx + 1}]"
            # Find text after this marker until the next marker or end
            pattern = rf"\[P{idx + 1}\]\s*(.*?)(?=\[P\d+\]|$)"
            match = re.search(pattern, response, re.DOTALL)

            if match:
                result.append(match.group(1).strip())
            else:
                # Fallback: empty translation if not found
                result.append("")

        return result
