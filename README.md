# sermon-translation

A CLI tool to translate Christian sermon notes from English to Mandarin Chinese (Simplified), preserving formatting and handling Bible verse references accurately.

## Features

- Translates DOCX sermon notes from English to Mandarin Chinese
- Fetches exact Bible verse translations from BibleGateway (CCB version by default)
- Preserves bold/italic formatting in the output document
- Auto-reviews the translation and applies corrections
- Supports separate models for translation and review
- Writes all logs to a rotating file (no console output)

## Requirements

- Python 3.10+
- [uv](https://github.com/astral-sh/uv)
- An [OpenRouter](https://openrouter.ai) API key

## Setup

```bash
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
uv sync
```

## Usage

```bash
uv run sermon-translate input.docx
```

The translated file is saved as `<input>-ChineseTranslation.docx` by default.

### Options

| Option | Description | Default |
|--------|-------------|---------|
| `-o, --output PATH` | Output file path | `<input>-ChineseTranslation.docx` |
| `--bible-version TEXT` | Chinese Bible version code | `CCB` |
| `--skip-review` | Skip the auto-review step | off |
| `--api-key TEXT` | OpenRouter API key | `$OPENROUTER_API_KEY` |
| `--model TEXT` | Model for translation | `DEFAULT_MODEL` from `.env` |
| `--review-model TEXT` | Model for review (can differ from translation model) | same as `--model` |

### Examples

```bash
# Basic usage
uv run sermon-translate sermon.docx

# Custom output path
uv run sermon-translate sermon.docx -o output/translated.docx

# Use a cheaper model for translation, stronger model for review
uv run sermon-translate sermon.docx \
  --model google/gemini-2.5-flash-lite \
  --review-model openai/gpt-4o

# Skip review
uv run sermon-translate sermon.docx --skip-review
```

## Configuration

All settings can be set in `.env` (copy from `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENROUTER_API_KEY` | OpenRouter API key | — |
| `OPENROUTER_BASE_URL` | API endpoint | `https://openrouter.ai/api/v1` |
| `DEFAULT_MODEL` | Translation model | `openai/gpt-4o` |
| `DEFAULT_REVIEW_MODEL` | Review model (falls back to `DEFAULT_MODEL`) | — |
| `TRANSLATION_TEMPERATURE` | Temperature for translation | `0.3` |
| `REVIEW_TEMPERATURE` | Temperature for review | `0.2` |
| `DEFAULT_BIBLE_VERSION` | BibleGateway version code | `CCB` |
| `LATIN_FONT` | Font for Latin text | `Microsoft YaHei` |
| `EAST_ASIAN_FONT` | Font for Chinese text | `Microsoft YaHei` |
| `FONT_SIZE_PT` | Font size in points | `14` |
| `MAX_TOKENS_PER_CHUNK` | Max tokens per translation chunk | `1500` |
| `MAX_PARAGRAPHS_PER_CHUNK` | Max paragraphs per chunk | `5` |
| `MAX_REVIEW_ITERATIONS` | Max review iterations | `2` |
| `LOG_FILE` | Log file path | `logs/sermon-translate.log` |

## Logging

All output is written to a log file (no console output). The log file rotates automatically:

- New file created when size reaches **100 MB**
- Log files older than **30 days** are deleted automatically
- Default location: `logs/sermon-translate.log` (relative to working directory)

To use a custom log path:

```bash
LOG_FILE=/var/log/sermon-translate.log uv run sermon-translate sermon.docx
```
