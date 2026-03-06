"""Service for interacting with the Mistral OCR API with annotation support."""

import base64
import logging
import time
from pathlib import Path
from typing import ClassVar

from mistralai import Mistral
from mistralai.extra import response_format_from_pydantic_model
from mistralai.models import SDKError

from mistral_ocr_extractor.config import Settings
from mistral_ocr_extractor.exceptions import ImageDecodeError, OCRAPIError
from mistral_ocr_extractor.models.annotations import BBoxAnnotation, DocumentAnnotation
from mistral_ocr_extractor.models.ocr import DocumentResult, ExtractedImage, PageResult

logger = logging.getLogger(__name__)

# Mapping of file extensions to MIME types
_MIME_TYPE_MAP: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}

_DEFAULT_MIME_TYPE = "image/jpeg"
_DATA_URI_PREFIX = "data:"


def _detect_mime_type(filename: str) -> str:
    """Detect MIME type from image filename extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return _MIME_TYPE_MAP.get(ext, _DEFAULT_MIME_TYPE)


def _strip_data_uri_prefix(raw_base64: str) -> tuple[str, str | None]:
    """
    Strip data URI prefix from a base64 string if present.

    Mistral returns image_base64 as: data:image/jpeg;base64,/9j/4AAQ...

    Returns:
        Tuple of (pure_base64_string, mime_type_or_none)
    """
    if not raw_base64.startswith(_DATA_URI_PREFIX):
        return raw_base64, None

    header, _, payload = raw_base64.partition(",")
    if not payload:
        return raw_base64, None

    mime_type = None
    header_content = header[len(_DATA_URI_PREFIX) :]
    if ";" in header_content:
        mime_type = header_content.split(";", 1)[0]

    return payload, mime_type


class OCRService:
    """
    Processes PDFs and images through Mistral OCR with annotations.

    For PDFs, handles the 8-page limit for document annotations by:
    1. First call: pages 0-7 with BOTH annotation types enabled.
    2. Subsequent calls: remaining pages with ONLY bbox annotations.
    3. Merges all page results into a single DocumentResult.

    For images, sends a single API call with bbox annotations only.

    Usage:
        service = OCRService(settings)
        result = service.process_pdf(Path("document.pdf"))
        result = service.process_image(Path("photo.jpg"))

    Raises:
        OCRAPIError: If any Mistral API call fails.
        ImageDecodeError: If base64 image data cannot be decoded.
    """

    MODEL: ClassVar[str] = "mistral-ocr-latest"
    DOC_ANNOTATION_PAGE_LIMIT: ClassVar[int] = 8

    def __init__(self, settings: Settings) -> None:
        self._client = Mistral(api_key=settings.mistral_api_key)
        self._bbox_format = response_format_from_pydantic_model(BBoxAnnotation)
        self._doc_format = response_format_from_pydantic_model(DocumentAnnotation)

    def process_pdf(self, pdf_path: Path) -> DocumentResult:
        """
        Process a single PDF file through Mistral OCR with annotations.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            DocumentResult with all pages, images, and annotations.

        Raises:
            OCRAPIError: If the Mistral API call fails.
            ImageDecodeError: If image decoding fails.
        """
        logger.info("Processing PDF: %s", pdf_path.name)
        start = time.monotonic()

        pdf_base64 = base64.b64encode(pdf_path.read_bytes()).decode("utf-8")
        document_url = f"data:application/pdf;base64,{pdf_base64}"

        # First call: first 8 pages with BOTH annotation types
        first_response = self._call_ocr(
            document_url=document_url,
            pages=list(range(self.DOC_ANNOTATION_PAGE_LIMIT)),
            include_doc_annotation=True,
            include_bbox_annotation=True,
            include_images=True,
        )

        document_annotation = first_response.document_annotation
        all_pages = self._extract_pages(first_response)
        total_api_pages = len(first_response.pages)

        # If document has more than 8 pages, process the rest
        if len(first_response.pages) == self.DOC_ANNOTATION_PAGE_LIMIT:
            remaining_response = self._call_ocr(
                document_url=document_url,
                pages=None,  # All pages
                include_doc_annotation=False,
                include_bbox_annotation=True,
                include_images=True,
            )

            # Only take pages beyond what we already have
            for page in remaining_response.pages:
                if page.index >= self.DOC_ANNOTATION_PAGE_LIMIT:
                    all_pages.append(self._extract_single_page(page))
                    total_api_pages += 1

        image_count = sum(len(p.images) for p in all_pages)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Completed %s: %d pages, %d images in %dms",
            pdf_path.name,
            total_api_pages,
            image_count,
            elapsed_ms,
        )

        return DocumentResult(
            source_filename=pdf_path.name,
            page_count=total_api_pages,
            image_count=image_count,
            pages=all_pages,
            document_annotation=document_annotation,
        )

    def process_image(self, image_path: Path) -> DocumentResult:
        """
        Process a single image file through Mistral OCR with bbox annotations.

        Args:
            image_path: Path to the image file (jpg, png, gif, webp).

        Returns:
            DocumentResult with a single page and bbox annotations.

        Raises:
            OCRAPIError: If the Mistral API call fails.
            ImageDecodeError: If image decoding fails.
        """
        logger.info("Processing image: %s", image_path.name)
        start = time.monotonic()

        mime_type = _detect_mime_type(image_path.name)
        img_base64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
        image_url = f"data:{mime_type};base64,{img_base64}"

        response = self._call_ocr_image(image_url=image_url)

        all_pages = self._extract_pages(response)
        image_count = sum(len(p.images) for p in all_pages)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        logger.info(
            "Completed %s: %d pages, %d images in %dms",
            image_path.name,
            len(all_pages),
            image_count,
            elapsed_ms,
        )

        return DocumentResult(
            source_filename=image_path.name,
            page_count=len(all_pages),
            image_count=image_count,
            pages=all_pages,
            document_annotation=getattr(response, "document_annotation", None),
        )

    def _call_ocr_image(self, image_url: str):
        """
        Make a single call to the Mistral OCR API with an image input.

        Raises:
            OCRAPIError: If the API call fails.
        """
        kwargs: dict = {
            "model": self.MODEL,
            "document": {
                "type": "image_url",
                "image_url": image_url,
            },
            "include_image_base64": True,
            "bbox_annotation_format": self._bbox_format,
            "document_annotation_format": self._doc_format,
        }

        try:
            return self._client.ocr.process(**kwargs)
        except SDKError as e:
            raise OCRAPIError(
                f"Mistral OCR API error for image: {e}",
                status_code=getattr(e, "status_code", None),
            ) from e

    def _call_ocr(
        self,
        document_url: str,
        *,
        pages: list[int] | None,
        include_doc_annotation: bool,
        include_bbox_annotation: bool,
        include_images: bool,
    ):
        """
        Make a single call to the Mistral OCR API.

        Raises:
            OCRAPIError: If the API call fails.
        """
        kwargs: dict = {
            "model": self.MODEL,
            "document": {
                "type": "document_url",
                "document_url": document_url,
            },
            "include_image_base64": include_images,
        }

        if pages is not None:
            kwargs["pages"] = pages

        if include_bbox_annotation:
            kwargs["bbox_annotation_format"] = self._bbox_format

        if include_doc_annotation:
            kwargs["document_annotation_format"] = self._doc_format

        try:
            return self._client.ocr.process(**kwargs)
        except SDKError as e:
            raise OCRAPIError(
                f"Mistral OCR API error for document: {e}",
                status_code=getattr(e, "status_code", None),
            ) from e

    def _extract_pages(self, response) -> list[PageResult]:
        """Extract all pages from an OCR response."""
        return [self._extract_single_page(page) for page in response.pages]

    def _extract_single_page(self, page) -> PageResult:
        """
        Extract a single page's content and images.

        Raises:
            ImageDecodeError: If base64 image data cannot be decoded.
        """
        images: list[ExtractedImage] = []

        for image in page.images or []:
            if not image.image_base64:
                logger.debug(
                    "Skipping image %s on page %d: no base64 data",
                    image.id,
                    page.index,
                )
                continue

            pure_base64, uri_mime_type = _strip_data_uri_prefix(image.image_base64)

            try:
                image_data = base64.b64decode(pure_base64)
            except Exception as e:
                raise ImageDecodeError(
                    f"Failed to decode image {image.id} on page {page.index}"
                ) from e

            mime_type = uri_mime_type or _detect_mime_type(image.id)

            images.append(
                ExtractedImage(
                    filename=image.id,
                    data=image_data,
                    mime_type=mime_type,
                    page_index=page.index,
                    annotation=getattr(image, "image_annotation", None),
                )
            )

        return PageResult(
            index=page.index,
            markdown=page.markdown,
            images=images,
        )
