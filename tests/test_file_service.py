"""Tests for FileService and filename sanitization."""

from pathlib import Path

import pytest

from mistral_ocr_extractor.exceptions import FileWriteError
from mistral_ocr_extractor.models.ocr import DocumentResult, ExtractedImage, PageResult
from mistral_ocr_extractor.services.file_service import FileService, _sanitize_dirname


class TestSanitizeDirname:
    def test_strips_unir_prefix_and_language_suffix(self):
        result = _sanitize_dirname(
            "7931332_full_6678_Tema_1._Introducción_al_aprendizaje_automático_esl-ES.pdf"
        )
        assert result == "Tema_1._Introducción_al_aprendizaje_automático"

    def test_strips_prefix_only(self):
        result = _sanitize_dirname("123_full_456_SomeTopic.pdf")
        assert result == "SomeTopic"

    def test_strips_language_suffix_only(self):
        result = _sanitize_dirname("MyDocument_en-US.pdf")
        assert result == "MyDocument"

    def test_no_prefix_no_suffix(self):
        result = _sanitize_dirname("simple.pdf")
        assert result == "simple"

    def test_image_filename(self):
        result = _sanitize_dirname("photo.jpg")
        assert result == "photo"

    def test_image_with_prefix(self):
        result = _sanitize_dirname("123_full_456_diagram.png")
        assert result == "diagram"


class TestFileService:
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

    def test_writes_markdown_file(self, tmp_path):
        service = FileService(output_dir=tmp_path)
        result = self._make_result()
        doc_dir = service.write_result("proj", result, "# Hello")

        md_path = doc_dir / "content.md"
        assert md_path.exists()
        assert md_path.read_text() == "# Hello"

    def test_writes_images(self, tmp_path):
        service = FileService(output_dir=tmp_path)
        image = ExtractedImage(
            filename="img-0.jpeg",
            data=b"\xff\xd8\xff",
            mime_type="image/jpeg",
            page_index=0,
        )
        page = PageResult(index=0, markdown="", images=[image])
        result = self._make_result(pages=[page], image_count=1)

        doc_dir = service.write_result("proj", result, "content")

        img_path = doc_dir / "images" / "img-0.jpeg"
        assert img_path.exists()
        assert img_path.read_bytes() == b"\xff\xd8\xff"

    def test_creates_nested_directory_structure(self, tmp_path):
        service = FileService(output_dir=tmp_path)
        result = self._make_result()
        doc_dir = service.write_result("my-project", result, "# Test")

        assert doc_dir == tmp_path / "my-project" / "test"
        assert doc_dir.is_dir()
        assert (doc_dir / "images").is_dir()

    def test_returns_doc_dir_path(self, tmp_path):
        service = FileService(output_dir=tmp_path)
        result = self._make_result(source_filename="123_full_456_Topic_en-US.pdf")
        doc_dir = service.write_result("proj", result, "")

        assert doc_dir == tmp_path / "proj" / "Topic"

    def test_multiple_images_across_pages(self, tmp_path):
        service = FileService(output_dir=tmp_path)
        img1 = ExtractedImage(
            filename="img-0.jpeg", data=b"\xff", mime_type="image/jpeg", page_index=0
        )
        img2 = ExtractedImage(
            filename="img-1.png", data=b"\x89", mime_type="image/png", page_index=1
        )
        pages = [
            PageResult(index=0, markdown="", images=[img1]),
            PageResult(index=1, markdown="", images=[img2]),
        ]
        result = self._make_result(pages=pages, page_count=2, image_count=2)

        doc_dir = service.write_result("proj", result, "content")

        assert (doc_dir / "images" / "img-0.jpeg").exists()
        assert (doc_dir / "images" / "img-1.png").exists()
