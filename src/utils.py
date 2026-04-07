"""
Utility functions for PDF card extraction.
"""

import logging
import os
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:
    Image = None

from config import (
    PDF_INPUT_DIR,
    CARDS_OUTPUT_DIR,
    LOGS_DIR,
    DPI_FOR_CONVERSION,
    IMAGE_FORMAT,
    TACTICAL_THEMES,
)

# Theme-specific starting pages (0-indexed, skipping unnecessary cover/intro pages)
THEME_START_PAGES = {
    "Idea_Tactics": 3,
    "Productivity_Tactics": 2,
    "Retrospective_Tactics": 1,
    "Storyteller_Tactics": 1,
    "Strategy_Tactics": 4,
    "Team_Tactics": 3,
    "Workshop_Tactics": 2,
}

# Theme-specific ending pages (0-indexed, page before credit pages start)
# For PDFs with no credit pages, use None to process all pages
THEME_END_PAGES = {
    "Idea_Tactics": 110,  # Credit pages start at page 112 (1-indexed)
    "Productivity_Tactics": None,  # No credit pages
    "Retrospective_Tactics": None,  # No credit pages
    "Storyteller_Tactics": 55,  # Credit pages start at page 56 (1-indexed)
    "Strategy_Tactics": 111,  # Credit pages start at page 113 (1-indexed)
    "Team_Tactics": 110,  # Credit pages start at page 112 (1-indexed)
    "Workshop_Tactics": 56,  # Credit pages start at page 57 (1-indexed)
}


def validate_dependencies() -> bool:
    """Validate that required dependencies are installed."""
    if fitz is None:
        raise ImportError("PyMuPDF (fitz) is not installed. Install with: pip install PyMuPDF")
    if Image is None:
        raise ImportError("Pillow is not installed. Install with: pip install Pillow")
    return True


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Set up logging configuration."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logger = logging.getLogger("utils")
    logger.setLevel(log_level)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # File handler
    log_file = LOGS_DIR / "extraction.log"
    file_handler = logging.FileHandler(log_file, mode='w')
    file_handler.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


def get_pdf_files() -> List[Tuple[str, str]]:
    """Get list of PDF files from input directory."""
    pdf_files = []
    if not PDF_INPUT_DIR.exists():
        return pdf_files
    
    for pdf_file in PDF_INPUT_DIR.glob("*.pdf"):
        theme_name = pdf_file.stem
        if theme_name in TACTICAL_THEMES:
            pdf_files.append((str(pdf_file), theme_name))
    
    return sorted(pdf_files)


def extract_cards_from_pdf(pdf_path: str, theme_name: str, logger: logging.Logger = None) -> List[Tuple[str, str]]:
    """
    Extract complete card images from a PDF file.
    Handles two different layouts:
    1. Single-column PDFs: Front and back on consecutive pages (need to be combined)
    2. Two-column PDFs: Front and back on same page (need to be split vertically)
    
    Args:
        pdf_path: Path to the PDF file
        theme_name: Name of the tactical theme
        logger: Optional logger instance
    
    Returns:
        List of tuples (card_path, card_name) for extracted cards
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    extracted_cards = []
    
    if fitz is None or Image is None:
        logger.error("PyMuPDF (fitz) or Pillow not installed. Cannot extract cards.")
        return extracted_cards
    
    try:
        logger.info(f"Processing PDF: {pdf_path}")
        pdf_document = fitz.open(pdf_path)
        total_pages = pdf_document.page_count
        logger.info(f"PDF has {total_pages} pages")
        
        # Detect layout type from first content page (skip cover)
        # Covers are typically page 0 or have unusual dimensions (>400px wide or >600px tall)
        page_width = None
        is_two_column = False
        
        for i in range(1, min(5, total_pages)):  # Start from page 1 to skip covers
            page = pdf_document[i]
            rect = page.rect
            # Standard content pages are either 252px (single-column) or 504px (two-column) wide
            if rect.width in range(240, 520):  # Standard content width range
                page_width = rect.width
                is_two_column = page_width > 400  # Two-column layout has ~504px width
                logger.info(f"Detected layout: {'Two-column (front+back per page)' if is_two_column else 'Single-column (front/back on consecutive pages)'}")
                break
        
        # Fallback: if no standard content page found, use page 0 (but skip if it looks like a cover)
        if page_width is None and total_pages > 0:
            page = pdf_document[0]
            rect = page.rect
            if 240 < rect.width < 520:  # Normal content width
                page_width = rect.width
                is_two_column = page_width > 400
                logger.info(f"Detected layout: {'Two-column (front+back per page)' if is_two_column else 'Single-column (front/back on consecutive pages)'}")
            else:
                # Assume single-column for unrecognized formats
                is_two_column = False
                logger.info("Detected layout: Single-column (front/back on consecutive pages) [default]")
        
        if is_two_column:
            extracted_cards = _extract_cards_two_column(pdf_document, theme_name, logger)
        else:
            extracted_cards = _extract_cards_single_column(pdf_document, theme_name, logger)
        
        pdf_document.close()
        logger.info(f"Successfully extracted {len(extracted_cards)} card(s) from {pdf_path}")
        
    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {e}")
    
    return extracted_cards


def _extract_cards_single_column(pdf_document, theme_name: str, logger: logging.Logger) -> List[Tuple[str, str]]:
    """
    Extract cards from single-column PDFs (front/back on consecutive pages).
    Combines pairs of pages horizontally to create complete cards.
    Uses theme-specific starting page to skip unnecessary cover/intro pages.
    If starting page is odd, pairs it with the next page to form the first card.
    """
    extracted_cards = []
    total_pages = pdf_document.page_count
    card_count = 0
    
    # Get theme-specific starting page (defaults to 1 if not found)
    start_page = THEME_START_PAGES.get(theme_name, 1)
    # Get theme-specific ending page (defaults to total_pages - 1 if not found)
    end_page = THEME_END_PAGES.get(theme_name, total_pages - 1)
    if end_page is None:
        end_page = total_pages
    logger.info(f"Starting extraction from page {start_page + 1} (0-indexed: {start_page})")
    
    page_num = start_page
    
    while page_num < end_page:
        try:
            page = pdf_document[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(DPI_FOR_CONVERSION/72, DPI_FOR_CONVERSION/72))
            
            # Use default card name
            card_name = f"{theme_name}_card{card_count + 1}"
            
            # Check if we should combine with next page or save as single
            if page_num == total_pages - 2:
                # Last page - save as single card
                card_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                card_path = CARDS_OUTPUT_DIR / f"{theme_name}_card{(card_count + 1):02d}.png"
                card_image.save(str(card_path), IMAGE_FORMAT)
                logger.info(f"Extracted card {card_count + 1} ('{card_name}') from page {page_num + 1} ({pix.width}x{pix.height})")
                extracted_cards.append((str(card_path), card_name))
                card_count += 1
                page_num += 1
            else:
                # Combine current and next page
                next_page = pdf_document[page_num + 1]
                next_pix = next_page.get_pixmap(matrix=fitz.Matrix(DPI_FOR_CONVERSION/72, DPI_FOR_CONVERSION/72))
                
                combined_width = pix.width + next_pix.width
                max_height = max(pix.height, next_pix.height)
                
                front_image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                back_image = Image.frombytes("RGB", (next_pix.width, next_pix.height), next_pix.samples)
                
                combined = Image.new("RGB", (combined_width, max_height), color="white")
                combined.paste(front_image, (0, 0))
                combined.paste(back_image, (pix.width, 0))
                
                card_path = CARDS_OUTPUT_DIR / f"{theme_name}_card{(card_count + 1):02d}.png"
                combined.save(str(card_path), IMAGE_FORMAT)
                
                logger.info(f"Extracted card {card_count + 1} ('{card_name}') from pages {page_num + 1}-{page_num + 2} (combined: {combined_width}x{max_height})")
                extracted_cards.append((str(card_path), card_name))
                card_count += 1
                page_num += 2
                
        except Exception as e:
            logger.error(f"Error processing page {page_num + 1}: {e}")
            page_num += 1
    
    return extracted_cards


def _extract_cards_two_column(pdf_document, theme_name: str, logger: logging.Logger) -> List[Tuple[str, str]]:
    """
    Extract cards from two-column PDFs (front+back on same page, side by side).
    Splits each page vertically into left (front) and right (back) halves, then
    pairs left+right from the SAME page to create complete cards.
    Uses theme-specific starting page to skip unnecessary cover/intro pages.
    """
    extracted_cards = []
    total_pages = pdf_document.page_count
    card_count = 0
    
    # Get theme-specific starting page (defaults to 1 if not found)
    start_page = THEME_START_PAGES.get(theme_name, 1)
    # Get theme-specific ending page (defaults to total_pages - 1 if not found)
    end_page = THEME_END_PAGES.get(theme_name, total_pages - 1)
    if end_page is None:
        end_page = total_pages
    logger.info(f"Starting extraction from page {start_page + 1} (0-indexed: {start_page})")

    # Helper: safely concatenate two images horizontally, padding to same height if needed
    def safe_concat_horiz(a, b):
        try:
            a_rgb = a.convert("RGB")
            b_rgb = b.convert("RGB")
            aw, ah = a_rgb.size
            bw, bh = b_rgb.size
            logger.debug(f"safe_concat_horiz: a.size={a_rgb.size}, b.size={b_rgb.size}")
            h = max(ah, bh)
            new = Image.new("RGB", (aw + bw, h), color="white")
            new.paste(a_rgb, (0, 0))
            new.paste(b_rgb, (aw, 0))
            return new
        except Exception as ex:
            logger.warning(f"safe_concat_horiz primary method failed: {ex}")
            try:
                h = max(a.size[1], b.size[1])
                a2 = a.convert("RGB").resize((a.size[0], h))
                b2 = b.convert("RGB").resize((b.size[0], h))
                logger.debug(f"safe_concat_horiz fallback resize: a2.size={a2.size}, b2.size={b2.size}")
                new = Image.new("RGB", (a2.size[0] + b2.size[0], h), color="white")
                new.paste(a2, (0, 0))
                new.paste(b2, (a2.size[0], 0))
                return new
            except Exception as ex2:
                logger.error(f"safe_concat_horiz fallback failed: {ex2}")
                return Image.new("RGB", (1, 1), color="white")

    # Process each page: split left/right and pair them as a single card
    for page_num in range(start_page, end_page):
        try:
            page = pdf_document[page_num]
            # Use page coordinates (points) for clipping
            page_rect = page.rect
            half_x = page_rect.width / 2.0

            # Split vertically in page coordinates: left half (front) and right half (back)
            front_rect = fitz.Rect(0, 0, half_x, page_rect.height)
            back_rect = fitz.Rect(half_x, 0, page_rect.width, page_rect.height)

            # Use default card name
            card_name = f"{theme_name}_card{card_count + 1}"

            # Render clipped pixmaps with the DPI matrix
            matrix = fitz.Matrix(DPI_FOR_CONVERSION / 72.0, DPI_FOR_CONVERSION / 72.0)
            front_pix = page.get_pixmap(matrix=matrix, clip=front_rect)
            front_image = Image.frombytes("RGB", (front_pix.width, front_pix.height), front_pix.samples)

            back_pix = page.get_pixmap(matrix=matrix, clip=back_rect)
            back_image = Image.frombytes("RGB", (back_pix.width, back_pix.height), back_pix.samples)

            # Pair front and back from the same page
            logger.debug(f"Pairing front+back from same page {page_num + 1}: front {front_image.size} vs back {back_image.size}")
            combined = safe_concat_horiz(front_image, back_image)
            
            card_path = CARDS_OUTPUT_DIR / f"{theme_name}_card{(card_count + 1):02d}.png"
            try:
                combined.save(str(card_path), IMAGE_FORMAT)
                logger.info(f"Extracted card {card_count + 1} ('{card_name}') from page {page_num + 1} (front+back combined)")
                extracted_cards.append((str(card_path), card_name))
                card_count += 1
            except Exception as ex:
                logger.error(f"Failed to save combined card for page {page_num + 1}: {ex}")

        except Exception as e:
            logger.error(f"Error extracting card from page {page_num + 1}: {e}")

    return extracted_cards


def create_extraction_summary(extraction_results: dict, logger: logging.Logger = None) -> str:
    """
    Create a summary report of the extraction process.
    
    Args:
        extraction_results: Dictionary with theme names as keys and list of extracted cards as values
        logger: Optional logger instance
    
    Returns:
        Path to the generated summary file
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    summary_path = Path(CARDS_OUTPUT_DIR).parent / "metadata" / "extraction_summary.txt"
    names_path = Path(CARDS_OUTPUT_DIR).parent / "metadata" / "card_names.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    total_cards = 0
    card_names = {}
    
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("CARD EXTRACTION SUMMARY\n")
        f.write("=" * 60 + "\n\n")
        
        for theme_name in sorted(extraction_results.keys()):
            cards = extraction_results[theme_name]
            total_cards += len(cards)
            
            f.write(f"{theme_name}: {len(cards)} card(s) extracted\n")
            for card_path, card_name in cards:
                filename = Path(card_path).name
                f.write(f"  - {filename} -> {card_name}\n")
                card_names[filename] = card_name
            f.write("\n")
        
        f.write("=" * 60 + "\n")
        f.write(f"TOTAL CARDS EXTRACTED: {total_cards}\n")
        f.write("=" * 60 + "\n")
    
    # Save JSON mapping (disabled to preserve manual card_names.json)
    # import json
    # with open(names_path, 'w', encoding='utf-8') as f:
    #     json.dump(card_names, f, indent=2, ensure_ascii=False)

    logger.info(f"Summary report created: {summary_path}")
    # logger.info(f"Card names JSON created: {names_path}")
    return str(summary_path)
