# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CLI tool that extracts structured markdown and images from PDFs using the Mistral OCR API with annotation support (document-level and per-image bounding box annotations). Built for processing UNIR university course material PDFs.

## Commands

```bash
# Install dependencies (uses uv with Python 3.12)
uv sync

# Run the extractor
uv run extract --path <folder-with-pdfs> [--name <project-name>] [-v]

# Example
uv run extract --path ./pdfs --name "my-course" --verbose
```

There is no test suite or linter configured.

## Architecture

The project follows a service-oriented pattern with three services orchestrated by the CLI entry point (`cli.py`).

**Pipeline flow:** `CLI → OCRService → MarkdownService → FileService`

1. **`cli.py`** — Entry point (`extract` command). Discovers PDFs in the given folder, iterates over them, skips already-processed ones (checks for existing `content.md`), and orchestrates the three services.

2. **`services/ocr_service.py`** — Calls Mistral OCR API. Handles the **8-page limit for document annotations** by splitting into two API calls: pages 0-7 with both annotation types, then remaining pages with bbox annotations only. Decodes base64 images from the response.

3. **`services/markdown_service.py`** — Builds a markdown document with TOML frontmatter (source metadata + document annotation) and page-separated content. Rewrites image paths to `images/` subfolder and inserts bbox annotations as HTML comments.

4. **`services/file_service.py`** — Writes output to disk. Sanitizes UNIR PDF filenames by stripping numeric prefixes (`\d+_full_\d+_`) and language suffixes (`_esl-ES`).

**Models (`models/`):**
- `annotations.py` — Pydantic schemas (`BBoxAnnotation`, `DocumentAnnotation`) sent to Mistral as structured annotation formats.
- `ocr.py` — Internal result models (`DocumentResult`, `PageResult`, `ExtractedImage`).

**Output structure:**
```
output/<project_name>/<sanitized_pdf_name>/content.md
output/<project_name>/<sanitized_pdf_name>/images/img-0.jpeg
```

## Configuration

- `MISTRAL_API_KEY` env var required (loaded from `.env` via python-dotenv)
- Settings in `config.py`: model name (`mistral-ocr-latest`), output directory (`output/`), annotation page limit (8)

## Key Dependencies

- `mistralai` — Mistral API client (uses `response_format_from_pydantic_model` for annotation schemas)
- `pydantic` — Data models and API schema generation
- `python-dotenv` — Environment variable loading
