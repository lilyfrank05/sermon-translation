"""CLI entry point for the sermon translator."""

import sys
from pathlib import Path

import click
from loguru import logger

from .bible_fetcher import BibleFetcher
from .config import DEFAULT_BIBLE_VERSION, DEFAULT_MODEL, DEFAULT_REVIEW_MODEL, LOG_FILE, OPENROUTER_API_KEY
from .docx_handler import get_plain_text, parse_translated_text, read_docx, write_docx
from .reviewer import Reviewer, format_review_report
from .translator import Translator


def _setup_logging():
    logger.remove()  # Remove default stderr sink
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_path,
        rotation="100 MB",
        retention="30 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}",
    )
    logger.add(sys.stderr, level="ERROR", format="{level}: {message}")


@click.command()
@click.argument("input_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file path (default: <input>-Chinese Translation.docx)",
)
@click.option(
    "--bible-version",
    default=DEFAULT_BIBLE_VERSION,
    help=f"Chinese Bible version code (default: {DEFAULT_BIBLE_VERSION})",
)
@click.option(
    "--skip-review",
    is_flag=True,
    help="Skip the auto-review step",
)
@click.option(
    "--api-key",
    envvar="OPENROUTER_API_KEY",
    help="OpenRouter API key (or set OPENROUTER_API_KEY env var)",
)
@click.option(
    "--model",
    default=DEFAULT_MODEL,
    help=f"Model to use for translation (default: {DEFAULT_MODEL})",
)
@click.option(
    "--review-model",
    default=None,
    help=f"Model to use for review (default: same as --model or {DEFAULT_REVIEW_MODEL})",
)
def main(
    input_file: Path,
    output: Path | None,
    bible_version: str,
    skip_review: bool,
    api_key: str | None,
    model: str,
    review_model: str | None,
):
    """
    Translate a sermon notes DOCX file from English to Mandarin Chinese.

    INPUT_FILE: Path to the input DOCX file (English)
    """
    _setup_logging()

    # Validate API key
    effective_api_key = api_key or OPENROUTER_API_KEY
    if not effective_api_key:
        logger.error("OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key")
        sys.exit(1)

    # Validate input file
    if not input_file.suffix.lower() == ".docx":
        logger.error(f"Input file must be a .docx file, got: {input_file.suffix}")
        sys.exit(1)

    # Generate output filename if not provided
    if output is None:
        output_file = input_file.parent / f"{input_file.stem}-ChineseTranslation.docx"
    else:
        output_file = output

    # Remove all .docx files except the input file
    for docx_file in input_file.parent.glob("*.docx"):
        if docx_file.resolve() != input_file.resolve():
            docx_file.unlink()
            logger.info(f"Removed: {docx_file}")

    logger.info(f"Reading: {input_file}")
    logger.info(f"Output will be: {output_file}")

    # Step 1: Read the DOCX file
    try:
        paragraphs = read_docx(input_file)
    except Exception as e:
        logger.error(f"Error reading DOCX file: {e}")
        sys.exit(1)

    logger.info(f"Found {len(paragraphs)} paragraphs")

    # Step 2: Detect and fetch Bible verses
    logger.info("Detecting Bible verse references...")
    bible_fetcher = BibleFetcher(version=bible_version)
    full_text = get_plain_text(paragraphs)
    verses = bible_fetcher.fetch_all(full_text)

    if verses:
        logger.info(f"Found {len(verses)} Bible verse reference(s)")
        for ref in verses:
            logger.info(f"  - {ref}")
    else:
        logger.info("No Bible verse references detected")

    verse_table = bible_fetcher.format_verse_table(verses)

    # Step 3: Translate
    logger.info(f"Translating with {model}...")
    translator = Translator(api_key=effective_api_key, model=model)

    def translation_progress(current: int, total: int):
        logger.info(f"  Translating chunk {current}/{total}")

    translated_texts = translator.translate_paragraphs(
        paragraphs,
        verse_table=verse_table,
        progress_callback=translation_progress,
    )

    # Reconstruct translated text with markers for review
    translated_with_markers = "\n".join(
        f"[P{i+1}] {text}" for i, text in enumerate(translated_texts)
    )

    # Step 4: Review (unless skipped)
    if not skip_review:
        effective_review_model = review_model or DEFAULT_REVIEW_MODEL
        logger.info(f"Reviewing translation with {effective_review_model}...")
        reviewer = Reviewer(api_key=effective_api_key, model=effective_review_model)

        def review_progress(current: int, total: int):
            logger.info(f"  Review iteration {current}/{total}")

        final_translation, issues = reviewer.review_translation(
            original_text=full_text,
            translated_text=translated_with_markers,
            verse_table=verse_table,
            progress_callback=review_progress,
        )

        if issues:
            logger.info(format_review_report(issues))
            # Parse the corrected translation
            translated_texts = parse_translated_text(final_translation, len(paragraphs))
        else:
            logger.info("Translation approved - no issues found")
    else:
        logger.info("Skipping review (--skip-review)")

    # Step 5: Write output DOCX
    logger.info(f"Writing: {output_file}")
    try:
        write_docx(paragraphs, output_file, translated_texts)
    except Exception as e:
        logger.error(f"Error writing DOCX file: {e}")
        sys.exit(1)

    logger.info("Done!")


if __name__ == "__main__":
    main()
