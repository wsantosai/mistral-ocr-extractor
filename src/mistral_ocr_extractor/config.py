"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

from mistral_ocr_extractor.exceptions import ConfigurationError

load_dotenv()


class Settings:
    """Immutable application settings from environment."""

    def __init__(self) -> None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ConfigurationError(
                "MISTRAL_API_KEY is not set. "
                "Copy .env.example to .env and set your API key."
            )
        self.mistral_api_key: str = api_key
        self.ocr_model: str = "mistral-ocr-latest"
        self.output_dir: Path = Path("output")
        self.document_annotation_page_limit: int = 8
