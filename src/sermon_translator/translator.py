"""OpenRouter-based translation logic."""

from openai import OpenAI

from .config import (
    DEFAULT_MODEL,
    MAX_PARAGRAPHS_PER_CHUNK,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    TRANSLATION_SYSTEM_PROMPT,
    TRANSLATION_TEMPERATURE,
)
from .docx_handler import Paragraph


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

        Returns list of chunks, where each chunk is a list of (index, paragraph) tuples.
        """
        chunks = []
        current_chunk = []

        for i, para in enumerate(paragraphs):
            current_chunk.append((i, para))

            if len(current_chunk) >= MAX_PARAGRAPHS_PER_CHUNK:
                chunks.append(current_chunk)
                current_chunk = []

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _translate_chunk(
        self,
        chunk: list[tuple[int, Paragraph]],
        verse_table: str,
    ) -> list[str]:
        """
        Translate a chunk of paragraphs.

        Args:
            chunk: List of (index, paragraph) tuples
            verse_table: Formatted Bible verse reference table

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
        return self._parse_response(translated_text, chunk)

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
