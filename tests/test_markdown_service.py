"""Tests for MarkdownService."""

import json

import pytest

from mistral_ocr_extractor.exceptions import AnnotationParseError
from mistral_ocr_extractor.models.ocr import DocumentResult, ExtractedImage, PageResult
from mistral_ocr_extractor.services.markdown_service import (
    MarkdownService,
    _escape_toml_value,
    _format_toml_string_list,
)


class TestEscapeTomlValue:
    def test_plain_string(self):
        assert _escape_toml_value("hello") == "hello"

    def test_escapes_backslash(self):
        assert _escape_toml_value("a\\b") == "a\\\\b"

    def test_escapes_quotes(self):
        assert _escape_toml_value('say "hi"') == 'say \\"hi\\"'

    def test_replaces_newlines(self):
        assert _escape_toml_value("line1\nline2") == "line1 line2"

    def test_removes_carriage_returns(self):
        assert _escape_toml_value("line1\r\nline2") == "line1 line2"


class TestFormatTomlStringList:
    def test_empty_list(self):
        assert _format_toml_string_list([]) == "[]"

    def test_single_item(self):
        assert _format_toml_string_list(["a"]) == '["a"]'

    def test_multiple_items(self):
        result = _format_toml_string_list(["a", "b"])
        assert result == '["a", "b"]'

    def test_escapes_items(self):
        result = _format_toml_string_list(['say "hi"'])
        assert result == '["say \\"hi\\""]'


class TestMarkdownService:
    def _make_result(self, **overrides):
        defaults = dict(
            source_filename="test.pdf",
            page_count=1,
            image_count=0,
            pages=[PageResult(index=0, markdown="# Hello", images=[])],
            document_annotation=None,
        )
        defaults.update(overrides)
        return DocumentResult(**defaults)

    def test_basic_output_has_frontmatter_and_content(self):
        service = MarkdownService()
        result = self._make_result()
        md = service.build(result)

        assert md.startswith("---\n")
        assert 'source = "test.pdf"' in md
        assert "pages = 1" in md
        assert "images = 0" in md
        assert "annotations = false" in md
        assert "<!-- Page 1 -->" in md
        assert "# Hello" in md

    def test_document_annotation_in_frontmatter(self):
        service = MarkdownService()
        annotation = json.dumps({
            "language": "es",
            "summary": "A test document.",
            "topics": ["testing", "OCR"],
        })
        result = self._make_result(document_annotation=annotation)
        md = service.build(result)

        assert "annotations = true" in md
        assert "[document_annotation]" in md
        assert 'language = "es"' in md
        assert 'summary = "A test document."' in md
        assert 'topics = ["testing", "OCR"]' in md

    def test_malformed_annotation_raises(self):
        service = MarkdownService()
        result = self._make_result(document_annotation="not valid json{{{")

        with pytest.raises(AnnotationParseError, match="Failed to parse"):
            service.build(result)

    def test_image_paths_rewritten(self):
        service = MarkdownService()
        page = PageResult(
            index=0,
            markdown="![img-0.jpeg](img-0.jpeg)",
            images=[
                ExtractedImage(
                    filename="img-0.jpeg",
                    data=b"\xff",
                    mime_type="image/jpeg",
                    page_index=0,
                )
            ],
        )
        result = self._make_result(pages=[page], image_count=1)
        md = service.build(result)

        assert "](images/img-0.jpeg)" in md
        assert "](img-0.jpeg)" not in md

    def test_bbox_annotation_inserted(self):
        service = MarkdownService()
        page = PageResult(
            index=0,
            markdown="![img-0.jpeg](img-0.jpeg)",
            images=[
                ExtractedImage(
                    filename="img-0.jpeg",
                    data=b"\xff",
                    mime_type="image/jpeg",
                    page_index=0,
                    annotation='{"image_type": "graph", "description": "A chart"}',
                )
            ],
        )
        result = self._make_result(pages=[page], image_count=1)
        md = service.build(result)

        assert "<!-- bbox_annotation:" in md
        assert '"image_type": "graph"' in md

    def test_multiple_pages(self):
        service = MarkdownService()
        pages = [
            PageResult(index=0, markdown="Page one content", images=[]),
            PageResult(index=1, markdown="Page two content", images=[]),
        ]
        result = self._make_result(pages=pages, page_count=2)
        md = service.build(result)

        assert "<!-- Page 1 -->" in md
        assert "<!-- Page 2 -->" in md
        assert "Page one content" in md
        assert "Page two content" in md

    def test_partial_annotation_fields(self):
        service = MarkdownService()
        annotation = json.dumps({"language": "en"})
        result = self._make_result(document_annotation=annotation)
        md = service.build(result)

        assert 'language = "en"' in md
        assert "summary" not in md
        assert "topics" not in md
