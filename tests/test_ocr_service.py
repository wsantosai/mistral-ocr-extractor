"""Tests for OCRService — image and PDF processing."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from mistral_ocr_extractor.exceptions import ImageDecodeError, OCRAPIError
from mistral_ocr_extractor.services.ocr_service import (
    OCRService,
    _detect_mime_type,
    _strip_data_uri_prefix,
)


class TestDetectMimeType:
    def test_jpg(self):
        assert _detect_mime_type("img-0.jpg") == "image/jpeg"

    def test_jpeg(self):
        assert _detect_mime_type("img-0.jpeg") == "image/jpeg"

    def test_png(self):
        assert _detect_mime_type("img-0.png") == "image/png"

    def test_gif(self):
        assert _detect_mime_type("img-0.gif") == "image/gif"

    def test_webp(self):
        assert _detect_mime_type("img-0.webp") == "image/webp"

    def test_unknown_defaults_to_jpeg(self):
        assert _detect_mime_type("img-0.bmp") == "image/jpeg"

    def test_no_extension(self):
        assert _detect_mime_type("noext") == "image/jpeg"


class TestStripDataUriPrefix:
    def test_with_prefix(self):
        raw = "data:image/png;base64,iVBORw0KGgo="
        payload, mime = _strip_data_uri_prefix(raw)
        assert payload == "iVBORw0KGgo="
        assert mime == "image/png"

    def test_without_prefix(self):
        raw = "iVBORw0KGgo="
        payload, mime = _strip_data_uri_prefix(raw)
        assert payload == raw
        assert mime is None

    def test_data_prefix_no_comma(self):
        raw = "data:image/png;base64"
        payload, mime = _strip_data_uri_prefix(raw)
        assert payload == raw
        assert mime is None


class TestOCRServiceProcessImage:
    @pytest.fixture
    def service(self):
        settings = MagicMock()
        settings.mistral_api_key = "test-key"
        with patch("mistral_ocr_extractor.services.ocr_service.Mistral"):
            return OCRService(settings)

    def test_process_image_builds_correct_document_type(self, service, tmp_path):
        img_path = tmp_path / "test.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = "# OCR Result"
        mock_page.images = []

        mock_response = MagicMock()
        mock_response.pages = [mock_page]
        mock_response.document_annotation = None

        service._client.ocr.process.return_value = mock_response

        result = service.process_image(img_path)

        call_kwargs = service._client.ocr.process.call_args[1]
        assert call_kwargs["document"]["type"] == "image_url"
        assert call_kwargs["document"]["image_url"].startswith("data:image/png;base64,")
        assert "bbox_annotation_format" in call_kwargs
        assert "document_annotation_format" in call_kwargs

    def test_process_image_returns_document_result(self, service, tmp_path):
        img_path = tmp_path / "photo.jpg"
        img_path.write_bytes(b"\xff\xd8\xff\xe0")

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = "# Text from image"
        mock_page.images = []

        mock_response = MagicMock()
        mock_response.pages = [mock_page]
        mock_response.document_annotation = None

        service._client.ocr.process.return_value = mock_response

        result = service.process_image(img_path)

        assert result.source_filename == "photo.jpg"
        assert result.page_count == 1
        assert result.image_count == 0
        assert len(result.pages) == 1
        assert result.pages[0].markdown == "# Text from image"

    def test_process_image_api_error(self, service, tmp_path):
        from mistralai.models import SDKError

        img_path = tmp_path / "fail.png"
        img_path.write_bytes(b"\x89PNG")

        service._client.ocr.process.side_effect = SDKError(
            "API error", MagicMock(), "error"
        )

        with pytest.raises(OCRAPIError, match="Mistral OCR API error for image"):
            service.process_image(img_path)

    def test_process_image_uses_correct_mime_for_jpg(self, service, tmp_path):
        img_path = tmp_path / "photo.jpeg"
        img_path.write_bytes(b"\xff\xd8\xff")

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = ""
        mock_page.images = []

        mock_response = MagicMock()
        mock_response.pages = [mock_page]
        mock_response.document_annotation = None

        service._client.ocr.process.return_value = mock_response

        service.process_image(img_path)

        call_kwargs = service._client.ocr.process.call_args[1]
        assert "data:image/jpeg;base64," in call_kwargs["document"]["image_url"]


class TestOCRServiceProcessPdf:
    @pytest.fixture
    def service(self):
        settings = MagicMock()
        settings.mistral_api_key = "test-key"
        with patch("mistral_ocr_extractor.services.ocr_service.Mistral"):
            return OCRService(settings)

    def _make_mock_page(self, index, markdown="", images=None):
        page = MagicMock()
        page.index = index
        page.markdown = markdown
        page.images = images or []
        return page

    def test_process_pdf_short_document(self, service, tmp_path):
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 content")

        pages = [self._make_mock_page(i) for i in range(3)]
        mock_response = MagicMock()
        mock_response.pages = pages
        mock_response.document_annotation = '{"language": "en"}'

        service._client.ocr.process.return_value = mock_response

        result = service.process_pdf(pdf_path)

        assert result.source_filename == "doc.pdf"
        assert result.page_count == 3
        assert result.document_annotation == '{"language": "en"}'
        # Only one API call for short docs
        assert service._client.ocr.process.call_count == 1

    def test_process_pdf_long_document_splits_calls(self, service, tmp_path):
        pdf_path = tmp_path / "long.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 content")

        # First call returns exactly 8 pages (triggers second call)
        first_pages = [self._make_mock_page(i) for i in range(8)]
        first_response = MagicMock()
        first_response.pages = first_pages
        first_response.document_annotation = '{"language": "es"}'

        # Second call returns all 12 pages
        second_pages = [self._make_mock_page(i) for i in range(12)]
        second_response = MagicMock()
        second_response.pages = second_pages

        service._client.ocr.process.side_effect = [first_response, second_response]

        result = service.process_pdf(pdf_path)

        assert service._client.ocr.process.call_count == 2
        assert result.page_count == 12  # 8 from first + 4 from second
        assert result.document_annotation == '{"language": "es"}'

    def test_process_pdf_sends_document_url_type(self, service, tmp_path):
        pdf_path = tmp_path / "doc.pdf"
        pdf_path.write_bytes(b"%PDF")

        pages = [self._make_mock_page(0)]
        mock_response = MagicMock()
        mock_response.pages = pages
        mock_response.document_annotation = None

        service._client.ocr.process.return_value = mock_response

        service.process_pdf(pdf_path)

        call_kwargs = service._client.ocr.process.call_args[1]
        assert call_kwargs["document"]["type"] == "document_url"
        assert call_kwargs["document"]["document_url"].startswith("data:application/pdf;base64,")

    def test_process_pdf_api_error(self, service, tmp_path):
        from mistralai.models import SDKError

        pdf_path = tmp_path / "fail.pdf"
        pdf_path.write_bytes(b"%PDF")

        service._client.ocr.process.side_effect = SDKError(
            "API error", MagicMock(), "error"
        )

        with pytest.raises(OCRAPIError, match="Mistral OCR API error for document"):
            service.process_pdf(pdf_path)


class TestExtractImages:
    @pytest.fixture
    def service(self):
        settings = MagicMock()
        settings.mistral_api_key = "test-key"
        with patch("mistral_ocr_extractor.services.ocr_service.Mistral"):
            return OCRService(settings)

    def test_extracts_base64_image(self, service, tmp_path):
        img_data = b"\xff\xd8\xff"
        img_b64 = base64.b64encode(img_data).decode()

        mock_image = MagicMock()
        mock_image.id = "img-0.jpeg"
        mock_image.image_base64 = f"data:image/jpeg;base64,{img_b64}"
        mock_image.image_annotation = None

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = ""
        mock_page.images = [mock_image]

        page_result = service._extract_single_page(mock_page)

        assert len(page_result.images) == 1
        assert page_result.images[0].data == img_data
        assert page_result.images[0].mime_type == "image/jpeg"
        assert page_result.images[0].filename == "img-0.jpeg"

    def test_skips_image_without_base64(self, service):
        mock_image = MagicMock()
        mock_image.id = "img-0.jpeg"
        mock_image.image_base64 = None

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = ""
        mock_page.images = [mock_image]

        page_result = service._extract_single_page(mock_page)
        assert len(page_result.images) == 0

    def test_invalid_base64_raises(self, service):
        mock_image = MagicMock()
        mock_image.id = "img-0.jpeg"
        mock_image.image_base64 = "not-valid-base64!!!"
        mock_image.image_annotation = None

        mock_page = MagicMock()
        mock_page.index = 0
        mock_page.markdown = ""
        mock_page.images = [mock_image]

        with pytest.raises(ImageDecodeError, match="Failed to decode"):
            service._extract_single_page(mock_page)
