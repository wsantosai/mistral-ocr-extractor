"""CLI entry point for mistral-ocr-extractor."""

import argparse
import logging
import sys
from pathlib import Path

from mistral_ocr_extractor.config import Settings
from mistral_ocr_extractor.exceptions import ExtractorError, FileDiscoveryError
from mistral_ocr_extractor.services.file_service import FileService, _sanitize_dirname
from mistral_ocr_extractor.services.markdown_service import MarkdownService
from mistral_ocr_extractor.services.ocr_service import OCRService

SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
SUPPORTED_EXTENSIONS = {".pdf"} | SUPPORTED_IMAGE_EXTENSIONS


def _discover_files(folder: Path) -> list[Path]:
    """
    Find all supported files (PDFs and images) in the given folder.

    Raises:
        FileDiscoveryError: If the folder doesn't exist or contains no supported files.
    """
    if not folder.is_dir():
        raise FileDiscoveryError(f"Folder does not exist: {folder}")

    files = sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    )
    if not files:
        raise FileDiscoveryError(
            f"No supported files found in: {folder} "
            f"(supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))})"
        )

    return files


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract structured markdown and images from PDFs and images "
            "using Mistral OCR with annotations"
        ),
    )
    parser.add_argument(
        "--name",
        required=False,
        default=None,
        help=(
            "Project name for the output folder. "
            "Defaults to the parent folder name of --path."
        ),
    )
    parser.add_argument(
        "--path",
        required=True,
        type=Path,
        help="Path to folder containing PDF and/or image files to process",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    try:
        settings = Settings()
        files = _discover_files(args.path)

        # Default --name to the parent folder name of --path
        project_name = args.name or args.path.resolve().parent.name

        ocr_service = OCRService(settings)
        markdown_service = MarkdownService()
        file_service = FileService(output_dir=settings.output_dir)

        print(f"Found {len(files)} file(s) in {args.path}")
        print(f"Output: {settings.output_dir / project_name}")
        print()

        skipped = 0
        for i, file_path in enumerate(files, 1):
            # Skip already-processed files (content.md exists)
            doc_dir_name = _sanitize_dirname(file_path.name)
            existing_md = settings.output_dir / project_name / doc_dir_name / "content.md"
            if existing_md.exists():
                print(f"[{i}/{len(files)}] Skipping (already exists): {file_path.name}")
                skipped += 1
                continue

            print(f"[{i}/{len(files)}] Processing: {file_path.name}")

            is_image = file_path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
            if is_image:
                result = ocr_service.process_image(file_path)
            else:
                result = ocr_service.process_pdf(file_path)

            markdown = markdown_service.build(result)
            doc_dir = file_service.write_result(project_name, result, markdown)

            print(
                f"         -> {doc_dir} "
                f"({result.page_count} pages, {result.image_count} images)"
            )

        if skipped:
            print(f"\nSkipped {skipped} already-processed file(s).")

        print()
        print(f"Done. All results saved to {settings.output_dir / project_name}/")

    except ExtractorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
