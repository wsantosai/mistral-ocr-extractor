"""Tests for CLI file discovery and routing."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from mistral_ocr_extractor.cli import _discover_files, SUPPORTED_EXTENSIONS, SUPPORTED_IMAGE_EXTENSIONS
from mistral_ocr_extractor.exceptions import FileDiscoveryError


def test_discover_files_nonexistent_folder(tmp_path):
    with pytest.raises(FileDiscoveryError, match="Folder does not exist"):
        _discover_files(tmp_path / "nonexistent")


def test_discover_files_empty_folder(tmp_path):
    with pytest.raises(FileDiscoveryError, match="No supported files found"):
        _discover_files(tmp_path)


def test_discover_files_unsupported_only(tmp_path):
    (tmp_path / "notes.txt").write_text("hello")
    (tmp_path / "data.csv").write_text("a,b")
    with pytest.raises(FileDiscoveryError, match="No supported files found"):
        _discover_files(tmp_path)


def test_discover_files_finds_pdfs(tmp_path):
    (tmp_path / "doc1.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "doc2.pdf").write_bytes(b"%PDF-1.4")
    result = _discover_files(tmp_path)
    assert len(result) == 2
    assert all(f.suffix == ".pdf" for f in result)


def test_discover_files_finds_images(tmp_path):
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "diagram.png").write_bytes(b"\x89PNG")
    result = _discover_files(tmp_path)
    assert len(result) == 2


def test_discover_files_mixed(tmp_path):
    (tmp_path / "doc.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "photo.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "notes.txt").write_text("ignored")
    result = _discover_files(tmp_path)
    assert len(result) == 2
    names = {f.name for f in result}
    assert names == {"doc.pdf", "photo.jpg"}


def test_discover_files_sorted(tmp_path):
    (tmp_path / "b.png").write_bytes(b"\x89PNG")
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")
    result = _discover_files(tmp_path)
    assert result[0].name == "a.pdf"
    assert result[1].name == "b.png"


def test_discover_files_case_insensitive_extension(tmp_path):
    (tmp_path / "photo.JPG").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "doc.PDF").write_bytes(b"%PDF-1.4")
    result = _discover_files(tmp_path)
    assert len(result) == 2


def test_supported_image_extensions():
    assert ".jpg" in SUPPORTED_IMAGE_EXTENSIONS
    assert ".jpeg" in SUPPORTED_IMAGE_EXTENSIONS
    assert ".png" in SUPPORTED_IMAGE_EXTENSIONS
    assert ".gif" in SUPPORTED_IMAGE_EXTENSIONS
    assert ".webp" in SUPPORTED_IMAGE_EXTENSIONS


def test_supported_extensions_includes_pdf():
    assert ".pdf" in SUPPORTED_EXTENSIONS
