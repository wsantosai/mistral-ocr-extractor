"""Pydantic models defining the annotation schemas sent to Mistral OCR API."""

from enum import Enum

from pydantic import BaseModel, Field


class ImageType(str, Enum):
    """Classification of extracted bounding box content."""

    GRAPH = "graph"
    TABLE = "table"
    DIAGRAM = "diagram"
    PHOTO = "photo"
    FORMULA = "formula"
    TEXT = "text"
    OTHER = "other"


class BBoxAnnotation(BaseModel):
    """Schema for per-image/bbox annotation. Sent to Mistral as bbox_annotation_format."""

    image_type: ImageType = Field(
        ...,
        description="The type of content in this bounding box.",
    )
    description: str = Field(
        ...,
        description=(
            "A concise description of what this image/figure shows, "
            "in the document's language."
        ),
    )


class DocumentAnnotation(BaseModel):
    """Schema for whole-document annotation. Sent to Mistral as document_annotation_format."""

    language: str = Field(
        ...,
        description=(
            "The primary language of the document in ISO 639-1 code "
            "(e.g., 'es', 'en')."
        ),
    )
    topics: list[str] = Field(
        ...,
        description="A list of the main topics covered in the document.",
    )
    summary: str = Field(
        ...,
        description=(
            "A comprehensive summary of the document's content (3-5 sentences)."
        ),
    )
