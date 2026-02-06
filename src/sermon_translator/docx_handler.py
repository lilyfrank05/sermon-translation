"""DOCX file reading and writing with formatting preservation."""

from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt

from .config import EAST_ASIAN_FONT, FONT_SIZE_PT, LATIN_FONT


@dataclass
class Run:
    """A text segment with consistent formatting."""
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Paragraph:
    """A paragraph containing multiple runs."""
    runs: list[Run]

    @property
    def text(self) -> str:
        """Get the full text of the paragraph."""
        return "".join(run.text for run in self.runs)

    def is_empty(self) -> bool:
        """Check if the paragraph has no text content."""
        return not self.text.strip()


def read_docx(file_path: str | Path) -> list[Paragraph]:
    """
    Read a DOCX file and extract paragraphs with formatting.

    Args:
        file_path: Path to the input DOCX file

    Returns:
        List of Paragraph objects with formatting information
    """
    doc = Document(file_path)
    paragraphs = []

    for para in doc.paragraphs:
        runs = []
        for run in para.runs:
            if run.text:  # Only include non-empty runs
                runs.append(Run(
                    text=run.text,
                    bold=run.bold or False,
                    italic=run.italic or False,
                ))

        # Include paragraph even if empty (to preserve structure)
        paragraphs.append(Paragraph(runs=runs))

    return paragraphs


def _set_run_fonts(run) -> None:
    """
    Set fonts for a run: Calibri for Latin, Microsoft YaHei for Chinese.

    Args:
        run: A python-docx Run object
    """
    # Set Latin/ASCII font
    run.font.name = LATIN_FONT
    run.font.size = Pt(FONT_SIZE_PT)

    # Set East Asian font via XML (python-docx doesn't expose this directly)
    r_element = run._element
    rPr = r_element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), EAST_ASIAN_FONT)


def write_docx(
    paragraphs: list[Paragraph],
    output_path: str | Path,
    translated_texts: list[str],
) -> None:
    """
    Write translated content to a DOCX file, preserving formatting.

    Uses Calibri for English text and Microsoft YaHei for Chinese text.

    Args:
        paragraphs: Original paragraphs with formatting information
        output_path: Path for the output DOCX file
        translated_texts: List of translated text for each paragraph
    """
    doc = Document()

    # Set default font for the Normal style
    style = doc.styles["Normal"]
    style.font.name = LATIN_FONT
    style.font.size = Pt(FONT_SIZE_PT)
    # Set East Asian font for the style
    style_element = style._element
    rPr = style_element.get_or_add_rPr()
    rFonts = rPr.get_or_add_rFonts()
    rFonts.set(qn("w:eastAsia"), EAST_ASIAN_FONT)

    for i, (orig_para, translated_text) in enumerate(zip(paragraphs, translated_texts)):
        # Skip empty paragraphs entirely (no empty lines in output)
        if orig_para.is_empty() and not translated_text.strip():
            continue

        para = doc.add_paragraph()

        if not orig_para.runs:
            # Empty paragraph - just add the translated text (if any)
            if translated_text.strip():
                run = para.add_run(translated_text)
                _set_run_fonts(run)
            continue

        # Try to map translated text to original runs by proportion
        # This is a heuristic since translation changes text length
        if len(orig_para.runs) == 1:
            # Simple case: one run, apply its formatting to all translated text
            run = para.add_run(translated_text)
            run.bold = orig_para.runs[0].bold
            run.italic = orig_para.runs[0].italic
            _set_run_fonts(run)
        else:
            # Multiple runs: try to preserve formatting proportionally
            _apply_proportional_formatting(para, orig_para.runs, translated_text)

    doc.save(output_path)


def _apply_proportional_formatting(
    para,
    original_runs: list[Run],
    translated_text: str,
) -> None:
    """
    Apply formatting from original runs to translated text proportionally.

    This attempts to maintain bold/italic sections in roughly the same
    proportional positions as the original.
    """
    if not translated_text:
        return

    original_length = sum(len(r.text) for r in original_runs)
    if original_length == 0:
        run = para.add_run(translated_text)
        _set_run_fonts(run)
        return

    # Calculate proportional positions for each run
    translated_length = len(translated_text)
    current_pos = 0

    for i, orig_run in enumerate(original_runs):
        run_proportion = len(orig_run.text) / original_length

        if i == len(original_runs) - 1:
            # Last run gets remaining text
            run_text = translated_text[current_pos:]
        else:
            end_pos = current_pos + int(run_proportion * translated_length)
            run_text = translated_text[current_pos:end_pos]
            current_pos = end_pos

        if run_text:
            run = para.add_run(run_text)
            run.bold = orig_run.bold
            run.italic = orig_run.italic
            _set_run_fonts(run)


def get_plain_text(paragraphs: list[Paragraph]) -> str:
    """
    Get plain text from paragraphs with paragraph markers.

    Args:
        paragraphs: List of Paragraph objects

    Returns:
        Plain text with [P1], [P2], etc. markers
    """
    lines = []
    for i, para in enumerate(paragraphs, 1):
        text = para.text.strip()
        if text:
            lines.append(f"[P{i}] {text}")
        else:
            lines.append(f"[P{i}]")
    return "\n".join(lines)


def parse_translated_text(translated: str, num_paragraphs: int) -> list[str]:
    """
    Parse translated text with paragraph markers back into a list.

    Args:
        translated: Translated text with [P1], [P2], etc. markers
        num_paragraphs: Expected number of paragraphs

    Returns:
        List of translated text for each paragraph
    """
    import re

    # Extract text for each paragraph marker
    result = [""] * num_paragraphs

    # Pattern to match [P1], [P2], etc. and capture following text
    pattern = r"\[P(\d+)\]\s*(.*?)(?=\[P\d+\]|$)"
    matches = re.findall(pattern, translated, re.DOTALL)

    for num_str, text in matches:
        idx = int(num_str) - 1
        if 0 <= idx < num_paragraphs:
            result[idx] = text.strip()

    return result
