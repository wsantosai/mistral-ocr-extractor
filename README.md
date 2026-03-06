# Mistral OCR Extractor

CLI tool that extracts structured markdown and images from PDF and image files using the [Mistral OCR API](https://docs.mistral.ai/capabilities/document/). Designed for batch-processing university course material (UNIR), it produces clean markdown with TOML frontmatter, extracted images, and AI-generated annotations.

**Supported formats:** PDF, JPG, JPEG, PNG, GIF, WebP

## Features

- **Batch processing** — Point at a folder and extract all PDFs and images at once
- **Structured annotations** — Document-level summaries (language, topics, summary) and per-image bounding box annotations (type, description) via Mistral's structured output
- **Clean markdown output** — TOML frontmatter with metadata, page-separated content, and image references
- **Image extraction** — All embedded images decoded and saved alongside the markdown
- **Incremental processing** — Already-processed files are automatically skipped
- **UNIR filename cleanup** — Strips numeric prefixes and language suffixes from UNIR PDF filenames

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- A [Mistral API key](https://console.mistral.ai/)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd mistral-ocr-extractor

# Install dependencies
uv sync

# Configure your API key
cp .env.example .env
# Edit .env and set your MISTRAL_API_KEY
```

## Usage

```bash
# Basic usage — process all PDFs and images in a folder
uv run extract --path ./my-pdfs

# Specify a project name for the output folder
uv run extract --path ./my-pdfs --name "my-course"

# Enable verbose logging
uv run extract --path ./my-pdfs --name "my-course" --verbose

# Run tests
uv run pytest tests/ -v
```

### CLI Options

| Option | Required | Description |
|---|---|---|
| `--path` | Yes | Path to folder containing PDF and/or image files |
| `--name` | No | Project name for the output folder (defaults to parent folder name of `--path`) |
| `--verbose`, `-v` | No | Enable debug-level logging |

## Output Structure

```
output/
  <project-name>/
    <document-name>/
      content.md        # Markdown with TOML frontmatter
      images/
        img-0.jpeg      # Extracted images
        img-1.png
```

### Example `content.md`

```markdown
---
source = "Tema_1._Introduccion.pdf"
pages = 12
images = 5
annotations = true

[document_annotation]
language = "es"
summary = "Introduction to machine learning concepts..."
topics = ["supervised learning", "neural networks"]
---

<!-- Page 1 -->

# Introduction to Machine Learning

![img-0.jpeg](images/img-0.jpeg)
<!-- bbox_annotation: {"image_type": "diagram", "description": "..."} -->
```

## How It Works

1. **Discovery** — Finds all supported files (`.pdf`, `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`) in the specified folder
2. **OCR with annotations** — Sends each file to Mistral OCR API:
   - **PDFs**: First 8 pages with both document-level and bounding box annotations, remaining pages with bbox annotations only (Mistral's document annotation limit)
   - **Images**: Single API call with bounding box annotations
3. **Markdown generation** — Assembles TOML frontmatter + page content with image paths rewritten to the local `images/` subfolder
4. **File output** — Writes `content.md` and all extracted images to disk

## License

This project is for academic/personal use.
