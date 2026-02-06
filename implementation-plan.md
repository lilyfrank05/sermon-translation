# Sermon Translation Tool - Implementation Plan

## Overview
A Python CLI tool to translate Christian sermon notes from English to Mandarin Chinese (Simplified), preserving key formatting and handling Bible verse references appropriately.

## Tech Stack
- **Python** with **uv** for project management
- **python-docx** for reading/writing DOCX files
- **openai** Python SDK with **OpenRouter** as the backend (access to GPT-4o, Claude, etc.)
- **httpx** for fetching Bible verses from BibleGateway
- **python-dotenv** for loading configuration from `.env` file
- **Click** for CLI interface

## Project Structure
```
sermon-translation/
├── pyproject.toml           # uv project config
├── .env                     # Environment configuration (create from .env.example)
├── .env.example             # Example environment file with all settings
├── src/
│   └── sermon_translator/
│       ├── __init__.py
│       ├── main.py          # CLI entry point
│       ├── docx_handler.py  # DOCX read/write with formatting
│       ├── bible_fetcher.py # Fetch verses from BibleGateway
│       ├── translator.py    # OpenRouter translation logic
│       ├── reviewer.py      # Auto-review and correction
│       └── config.py        # Configuration loaded from .env
├── requirements.md          # (existing)
└── README.md               # Usage instructions
```

## Implementation Steps

### Step 1: Project Setup
- Initialize uv project with `uv init`
- Add dependencies: `python-docx`, `openai`, `click`
- Create package structure under `src/sermon_translator/`

### Step 2: DOCX Handler (`docx_handler.py`)
**Read functionality:**
- Extract paragraphs from input DOCX
- For each paragraph, extract "runs" (text segments with consistent formatting)
- Store formatting metadata (bold, italic) per run
- Return structured data: `List[Paragraph]` where each paragraph contains runs with text + formatting

**Write functionality:**
- Create new DOCX document
- Apply default styling (ignore source font size/family/paragraph gaps)
- Recreate paragraphs with translated text
- Reapply bold/italic formatting to corresponding runs

### Step 3: Bible Fetcher (`bible_fetcher.py`)
**Verse detection:**
- Use regex to detect Bible verse references in the source text
- Common patterns: "John 3:16", "Romans 8:28-30", "1 Corinthians 13:4-7", "Psalm 23:1"
- Handle various formats: book name + chapter:verse, verse ranges

**Fetch from BibleGateway:**
- URL format: `https://www.biblegateway.com/passage/?search={reference}&version=CCB`
- Parse HTML response to extract verse text
- Cache fetched verses to avoid duplicate requests
- Handle errors gracefully (network issues, invalid references)

**Returns:**
- Dictionary mapping English verse references to Chinese translations
- Example: `{"John 3:16": "因为上帝爱世人，甚至将祂独一的儿子赐给他们..."}`

### Step 4: Translator (`translator.py`)
**Pre-processing:**
- Detect all Bible verse references in the source text
- Fetch Chinese translations from BibleGateway
- Build a verse lookup table to provide to GPT

**System prompt with translation rules:**
```
You are translating Christian sermon notes from English to Mandarin Chinese (Simplified).

Rules:
1. When "he/He/Him/His" refers to God, translate to 祂
2. Translate "God" to 上帝, not 神 (unless it's a direct Bible quote)
3. Do not paraphrase - preserve original paragraph structure and meaning
4. Use natural, native Chinese expressions
5. For Bible verse quotations, use the EXACT Chinese text provided in the reference table below

[BIBLE VERSE REFERENCE TABLE]
{verse_table}
```

**Chunking strategy:**
- Group paragraphs into chunks using both token and paragraph limits
- Default: max 5 paragraphs OR ~1500 tokens per chunk (whichever is reached first)
- Token estimation uses heuristics: ~1.5 tokens per Chinese character, ~0.25 per English character
- Preserve paragraph boundaries (never split mid-paragraph)
- Include paragraph markers in prompt so translations align

**Retry mechanism:**
- After translating a chunk, check if any non-empty paragraphs got empty results
- If translations are missing (e.g., due to output truncation), retry those paragraphs individually
- Up to 2 retry attempts per missing paragraph

**API call:**
- Use `gpt-4o` model for high-quality translation
- Temperature ~0.3 for consistency
- Parse response to extract translated paragraphs

### Step 5: Auto-Review (`reviewer.py`)
**Review process:**
- After translation, send original + translated text to GPT for review
- Review in chunks (same chunking as translation)

**Review prompt:**
```
You are reviewing a Chinese translation of English sermon notes.

Check for:
1. Accuracy: Does the translation preserve the original meaning?
2. Naturalness: Does it sound like native Mandarin Chinese?
3. Consistency: Are theological terms translated consistently?
4. Bible verses: Are they quoted correctly from the provided reference?
5. Pronouns: Is 祂 used for God's pronouns? Is 上帝 used (not 神)?

For each issue found, provide:
- The problematic text
- The issue type
- A suggested correction

If the translation is good, respond with "APPROVED".
```

**Output:**
- List of issues with suggested corrections
- If issues found, automatically apply corrections and re-review (max 2 iterations)
- Final approval status

### Step 6: Main CLI (`main.py`)
```bash
uv run sermon-translate input.docx output.docx [--bible-version CCB] [--skip-review]
```
- Validate input file exists
- **Clean up existing .docx files** (removes all .docx files except the input file before processing)
- Read DOCX → structured paragraphs
- Detect and fetch Bible verses from BibleGateway
- Translate in chunks via OpenAI (with verse table)
- Auto-review translation and apply corrections
- Write translated content to output DOCX (**empty paragraphs are filtered out**)
- Report progress to user

### Step 7: Configuration (`config.py`)
All settings are loaded from `.env` file using python-dotenv:

**OpenRouter Settings:**
- `OPENROUTER_API_KEY` - API key for OpenRouter
- `OPENROUTER_BASE_URL` - API endpoint (default: https://openrouter.ai/api/v1)
- `DEFAULT_MODEL` - Model to use (default: openai/gpt-4o)
- `TRANSLATION_TEMPERATURE` - Temperature for translation (default: 0.3)
- `REVIEW_TEMPERATURE` - Temperature for review (default: 0.2)

**Bible Settings:**
- `DEFAULT_BIBLE_VERSION` - Chinese Bible version (default: CCB)
- `BIBLEGATEWAY_URL` - BibleGateway API URL

**Font Settings:**
- `LATIN_FONT` - Font for English text (default: Microsoft YaHei)
- `EAST_ASIAN_FONT` - Font for Chinese text (default: Microsoft YaHei)
- `FONT_SIZE_PT` - Font size in points (default: 14)

**Chunking Settings:**
- `MAX_TOKENS_PER_CHUNK` - Max tokens per translation chunk (default: 1500)
- `MAX_PARAGRAPHS_PER_CHUNK` - Max paragraphs per chunk (default: 5)
- `MAX_REVIEW_ITERATIONS` - Max review iterations (default: 2)

## Key Design Decisions

### Formatting Preservation
- **Preserved**: Bold, italic, paragraph breaks
- **Not preserved**: Font size, font family, paragraph spacing (use DOCX defaults)
- Implementation: Track run-level formatting, reapply after translation

### Bible Verse Handling
- Detect verse references using regex patterns for common Bible citation formats
- Fetch exact Chinese translations from BibleGateway.com (CCB version)
- Provide verse lookup table to GPT with instruction to use exact text
- This ensures 100% accuracy for Bible quotations (not relying on GPT's memory)

### Chunking Approach
- Translate in small groups (max 5 paragraphs or ~1500 tokens per chunk)
- Use both paragraph count and token estimation to prevent output truncation
- Use clear delimiters (e.g., `[P1]`, `[P2]`) to maintain alignment
- Automatically detect and retry any missing translations individually
- Validate output has same paragraph count as input

## Files to Create
1. `pyproject.toml` - Project configuration
2. `src/sermon_translator/__init__.py` - Package init
3. `src/sermon_translator/config.py` - Constants and settings
4. `src/sermon_translator/docx_handler.py` - DOCX I/O
5. `src/sermon_translator/bible_fetcher.py` - BibleGateway verse fetching
6. `src/sermon_translator/translator.py` - OpenAI translation
7. `src/sermon_translator/reviewer.py` - Auto-review and correction
8. `src/sermon_translator/main.py` - CLI entry point

## Verification Plan
1. Create a test sermon DOCX with:
   - Regular text paragraphs
   - Bold and italic formatting
   - Bible verse references
   - Pronouns referring to God
2. Run the translator
3. Verify output DOCX has:
   - Correct Mandarin translation
   - Preserved bold/italic formatting
   - 祂 used for God's pronouns
   - 上帝 used instead of 神
   - Proper paragraph structure

## Environment Setup
1. Copy `.env.example` to `.env`
2. Edit `.env` and set your `OPENROUTER_API_KEY`
3. Optionally adjust other settings (model, fonts, etc.)

```bash
cp .env.example .env
# Edit .env with your API key and preferences
```
