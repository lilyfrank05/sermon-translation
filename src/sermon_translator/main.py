"""CLI entry point for the sermon translator."""

import sys
from pathlib import Path

import click

from .bible_fetcher import BibleFetcher
from .config import DEFAULT_BIBLE_VERSION, DEFAULT_MODEL, OPENROUTER_API_KEY
from .docx_handler import get_plain_text, parse_translated_text, read_docx, write_docx
from .reviewer import Reviewer, format_review_report
from .translator import Translator


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
    help=f"Model to use (default: {DEFAULT_MODEL})",
)
def main(
    input_file: Path,
    output: Path | None,
    bible_version: str,
    skip_review: bool,
    api_key: str | None,
    model: str,
):
    """
    Translate a sermon notes DOCX file from English to Mandarin Chinese.

    INPUT_FILE: Path to the input DOCX file (English)
    """
    # Validate API key
    effective_api_key = api_key or OPENROUTER_API_KEY
    if not effective_api_key:
        click.echo("Error: OpenRouter API key required. Set OPENROUTER_API_KEY or use --api-key", err=True)
        sys.exit(1)

    # Validate input file
    if not input_file.suffix.lower() == ".docx":
        click.echo(f"Error: Input file must be a .docx file, got: {input_file.suffix}", err=True)
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
            click.echo(f"Removed: {docx_file}")

    click.echo(f"Reading: {input_file}")
    click.echo(f"Output will be: {output_file}")

    # Step 1: Read the DOCX file
    try:
        paragraphs = read_docx(input_file)
    except Exception as e:
        click.echo(f"Error reading DOCX file: {e}", err=True)
        sys.exit(1)

    click.echo(f"Found {len(paragraphs)} paragraphs")

    # Step 2: Detect and fetch Bible verses
    click.echo("Detecting Bible verse references...")
    bible_fetcher = BibleFetcher(version=bible_version)
    full_text = get_plain_text(paragraphs)
    verses = bible_fetcher.fetch_all(full_text)

    if verses:
        click.echo(f"Found {len(verses)} Bible verse reference(s)")
        for ref in verses:
            click.echo(f"  - {ref}")
    else:
        click.echo("No Bible verse references detected")

    verse_table = bible_fetcher.format_verse_table(verses)

    # Step 3: Translate
    click.echo(f"Translating with {model}...")
    translator = Translator(api_key=effective_api_key, model=model)

    def translation_progress(current: int, total: int):
        click.echo(f"  Translating chunk {current}/{total}")

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
        click.echo(f"Reviewing translation with {model}...")
        reviewer = Reviewer(api_key=effective_api_key, model=model)

        def review_progress(current: int, total: int):
            click.echo(f"  Review iteration {current}/{total}")

        final_translation, issues = reviewer.review_translation(
            original_text=full_text,
            translated_text=translated_with_markers,
            verse_table=verse_table,
            progress_callback=review_progress,
        )

        if issues:
            click.echo(format_review_report(issues))
            # Parse the corrected translation
            translated_texts = parse_translated_text(final_translation, len(paragraphs))
        else:
            click.echo("Translation approved - no issues found")
    else:
        click.echo("Skipping review (--skip-review)")

    # Step 5: Write output DOCX
    click.echo(f"Writing: {output_file}")
    try:
        write_docx(paragraphs, output_file, translated_texts)
    except Exception as e:
        click.echo(f"Error writing DOCX file: {e}", err=True)
        sys.exit(1)

    click.echo("Done!")


if __name__ == "__main__":
    main()
