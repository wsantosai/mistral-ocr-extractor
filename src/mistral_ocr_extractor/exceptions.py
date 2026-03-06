"""Custom exceptions for mistral-ocr-extractor. Fail loud and hard."""


class ExtractorError(Exception):
    """Base exception for all extractor errors."""


class ConfigurationError(ExtractorError):
    """Raised when configuration is missing or invalid."""


class OCRAPIError(ExtractorError):
    """Raised when the Mistral OCR API call fails."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class ImageDecodeError(ExtractorError):
    """Raised when base64 image data cannot be decoded."""


class FileWriteError(ExtractorError):
    """Raised when writing output files to disk fails."""


class FileDiscoveryError(ExtractorError):
    """Raised when the source folder has no supported files or doesn't exist."""


class AnnotationParseError(ExtractorError):
    """Raised when annotation JSON from Mistral cannot be parsed."""
