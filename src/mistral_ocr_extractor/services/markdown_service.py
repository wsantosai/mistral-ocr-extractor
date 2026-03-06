"""Service for building markdown documents with TOML frontmatter from OCR results."""

import json
import logging

from mistral_ocr_extractor.exceptions import AnnotationParseError
from mistral_ocr_extractor.models.ocr import DocumentResult

logger = logging.getLogger(__name__)


def _escape_toml_value(value: str) -> str:
    """Escape a string for use inside a TOML double-quoted basic string."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", " ")
        .replace("\r", "")
    )


def _format_toml_string_list(items: list[str]) -> str:
    """Format a list of strings as a TOML array."""
    escaped = [f'"{_escape_toml_value(item)}"' for item in items]
    return f"[{', '.join(escaped)}]"


class MarkdownService:
    """
    Builds a markdown document from OCR results.

    Responsibilities:
    - TOML frontmatter with source metadata and annotations
    - Page-separated markdown content
    - Image references pointing to images/ subfolder
    - Inline bbox annotation comments below each image

    Usage:
        service = MarkdownService()
        markdown_str = service.build(document_result)
    """

    def build(self, result: DocumentResult) -> str:
        """
        Build a complete markdown document from an OCR result.

        Args:
            result: The processed OCR result for a single PDF.

        Returns:
            Complete markdown string with TOML frontmatter.

        Raises:
            AnnotationParseError: If annotation JSON cannot be parsed.
        """
        parts: list[str] = []

        # Frontmatter
        parts.append(self._build_frontmatter(result))

        # Page content
        for page in result.pages:
            parts.append(f"<!-- Page {page.index + 1} -->")
            parts.append("")

            page_content = page.markdown

            # Replace image placeholders with relative paths to images/ folder
            # and insert bbox annotation comments below each image
            for image in page.images:
                # Mistral format: ![img-0.jpeg](img-0.jpeg)
                # Our format:     ![img-0.jpeg](images/img-0.jpeg)
                page_content = page_content.replace(
                    f"]({image.filename})",
                    f"](images/{image.filename})",
                )

                # Insert bbox annotation as HTML comment after the image reference
                if image.annotation:
                    image_ref = f"](images/{image.filename})"
                    annotation_comment = (
                        f"](images/{image.filename})\n"
                        f"<!-- bbox_annotation: {image.annotation} -->"
                    )
                    page_content = page_content.replace(
                        image_ref, annotation_comment
                    )

            parts.append(page_content)
            parts.append("")

        return "\n".join(parts)

    def _build_frontmatter(self, result: DocumentResult) -> str:
        """
        Build TOML frontmatter with source metadata and document annotation.

        Raises:
            AnnotationParseError: If document_annotation JSON is malformed.
        """
        lines: list[str] = [
            "---",
            f'source = "{_escape_toml_value(result.source_filename)}"',
            f"pages = {result.page_count}",
            f"images = {result.image_count}",
            f"annotations = {str(bool(result.document_annotation)).lower()}",
        ]

        if result.document_annotation:
            try:
                doc_ann = json.loads(result.document_annotation)
            except json.JSONDecodeError as e:
                raise AnnotationParseError(
                    f"Failed to parse document annotation for "
                    f"{result.source_filename}: {e}"
                ) from e

            lines.append("")
            lines.append("[document_annotation]")

            if "language" in doc_ann:
                lines.append(
                    f'language = "{_escape_toml_value(str(doc_ann["language"]))}"'
                )
            if "summary" in doc_ann:
                lines.append(
                    f'summary = "{_escape_toml_value(str(doc_ann["summary"]))}"'
                )
            if "topics" in doc_ann and isinstance(doc_ann["topics"], list):
                lines.append(
                    f"topics = {_format_toml_string_list(doc_ann['topics'])}"
                )

        lines.append("---")
        lines.append("")

        return "\n".join(lines)
