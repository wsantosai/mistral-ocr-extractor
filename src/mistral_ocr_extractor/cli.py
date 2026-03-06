"""CLI entry point for mistral-ocr-extractor."""

import argparse
import logging
import sys
from pathlib import Path

from mistral_ocr_extractor.config import Settings
from mistral_ocr_extractor.exceptions import ExtractorError, PDFDiscoveryError
from mistral_ocr_extractor.services.file_service import FileService, _sanitize_dirname
from mistral_ocr_extractor.services.markdown_service import MarkdownService
from mistral_ocr_extractor.services.ocr_service import OCRService


def _discover_pdfs(folder: Path) -> list[Path]:
    """
    Find all PDF files in the given folder.

    Raises:
        PDFDiscoveryError: If the folder doesn't exist or contains no PDFs.
    """
    if not folder.is_dir():
        raise PDFDiscoveryError(f"Folder does not exist: {folder}")

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        raise PDFDiscoveryError(f"No PDF files found in: {folder}")

    return pdfs


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Extract structured markdown and images from PDFs "
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
        help="Path to folder containing PDF files to process",
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
        pdfs = _discover_pdfs(args.path)

        # Default --name to the parent folder name of --path
        project_name = args.name or args.path.resolve().parent.name

        ocr_service = OCRService(settings)
        markdown_service = MarkdownService()
        file_service = FileService(output_dir=settings.output_dir)

        print(f"Found {len(pdfs)} PDF(s) in {args.path}")
        print(f"Output: {settings.output_dir / project_name}")
        print()

        skipped = 0
        for i, pdf_path in enumerate(pdfs, 1):
            # Skip already-processed PDFs (content.md exists)
            doc_dir_name = _sanitize_dirname(pdf_path.name)
            existing_md = settings.output_dir / project_name / doc_dir_name / "content.md"
            if existing_md.exists():
                print(f"[{i}/{len(pdfs)}] Skipping (already exists): {pdf_path.name}")
                skipped += 1
                continue

            print(f"[{i}/{len(pdfs)}] Processing: {pdf_path.name}")

            result = ocr_service.process_pdf(pdf_path)
            markdown = markdown_service.build(result)
            doc_dir = file_service.write_result(project_name, result, markdown)

            print(
                f"         -> {doc_dir} "
                f"({result.page_count} pages, {result.image_count} images)"
            )

        if skipped:
            print(f"\nSkipped {skipped} already-processed PDF(s).")

        print()
        print(f"Done. All results saved to {settings.output_dir / project_name}/")

    except ExtractorError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
