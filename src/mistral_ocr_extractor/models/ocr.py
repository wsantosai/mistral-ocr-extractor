"""Pydantic models for internal OCR processing results."""

from pydantic import BaseModel


class ExtractedImage(BaseModel):
    """A single image extracted from the OCR response."""

    filename: str
    data: bytes
    mime_type: str
    page_index: int
    annotation: str | None = None  # Raw JSON string from bbox_annotation


class PageResult(BaseModel):
    """Processed result for a single page."""

    index: int
    markdown: str
    images: list[ExtractedImage] = []


class DocumentResult(BaseModel):
    """Complete OCR result for a single PDF document."""

    source_filename: str
    page_count: int
    image_count: int
    pages: list[PageResult]
    document_annotation: str | None = None  # Raw JSON string from document_annotation
