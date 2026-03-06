"""Service for writing OCR results to the local filesystem."""

import logging
import re
from pathlib import Path

from mistral_ocr_extractor.exceptions import FileWriteError
from mistral_ocr_extractor.models.ocr import DocumentResult

logger = logging.getLogger(__name__)


def _sanitize_dirname(filename: str) -> str:
    """
    Create a clean directory name from a PDF filename.

    Strips the numeric prefix, file extension, and language suffix.
    Example: "7931332_full_6678_Tema_1._Introducción_al_aprendizaje_automático_esl-ES.pdf"
           -> "Tema_1._Introducción_al_aprendizaje_automático"
    """
    stem = Path(filename).stem

    # Strip common UNIR prefix pattern: digits_full_digits_
    stem = re.sub(r"^\d+_full_\d+_", "", stem)

    # Strip language suffix: _esl-ES, _en-US, etc.
    stem = re.sub(r"_[a-z]{2,3}-[A-Z]{2}$", "", stem)

    return stem


class FileService:
    """
    Writes OCR results (markdown + images) to the local filesystem.

    Output structure:
        output/<project_name>/<pdf_stem>/content.md
        output/<project_name>/<pdf_stem>/images/img-0.jpeg

    Usage:
        service = FileService(output_dir=Path("output"))
        service.write_result("my-project", document_result, markdown_content)

    Raises:
        FileWriteError: If any file write operation fails.
    """

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    def write_result(
        self,
        project_name: str,
        result: DocumentResult,
        markdown_content: str,
    ) -> Path:
        """
        Write a single document's OCR results to disk.

        Args:
            project_name: The project/folder name for grouping output.
            result: The processed OCR result.
            markdown_content: The rendered markdown string.

        Returns:
            Path to the created document directory.

        Raises:
            FileWriteError: If writing any file fails.
        """
        doc_dir_name = _sanitize_dirname(result.source_filename)
        doc_dir = self._output_dir / project_name / doc_dir_name
        images_dir = doc_dir / "images"

        try:
            images_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise FileWriteError(
                f"Failed to create directory {images_dir}"
            ) from e

        # Write markdown
        md_path = doc_dir / "content.md"
        try:
            md_path.write_text(markdown_content, encoding="utf-8")
        except OSError as e:
            raise FileWriteError(f"Failed to write {md_path}") from e

        logger.info("Wrote markdown: %s", md_path)

        # Write images
        for page in result.pages:
            for image in page.images:
                img_path = images_dir / image.filename
                try:
                    img_path.write_bytes(image.data)
                except OSError as e:
                    raise FileWriteError(
                        f"Failed to write image {img_path}"
                    ) from e

        image_count = sum(len(p.images) for p in result.pages)
        if image_count:
            logger.info("Wrote %d images to %s", image_count, images_dir)

        return doc_dir
