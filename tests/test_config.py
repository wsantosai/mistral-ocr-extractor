"""Tests for Settings configuration."""

from unittest.mock import patch

import pytest

from mistral_ocr_extractor.config import Settings
from mistral_ocr_extractor.exceptions import ConfigurationError


class TestSettings:
    def test_loads_api_key_from_env(self):
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "test-key-123"}):
            settings = Settings()
        assert settings.mistral_api_key == "test-key-123"

    def test_raises_when_api_key_missing(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ConfigurationError, match="MISTRAL_API_KEY"):
                Settings()

    def test_default_values(self):
        with patch.dict("os.environ", {"MISTRAL_API_KEY": "key"}):
            settings = Settings()
        assert settings.ocr_model == "mistral-ocr-latest"
        assert str(settings.output_dir) == "output"
        assert settings.document_annotation_page_limit == 8
