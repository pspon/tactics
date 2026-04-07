"""
Main script for extracting card images from tactical theme PDFs.
"""

import argparse
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from config import PDF_INPUT_DIR, CARDS_OUTPUT_DIR, LOGS_DIR
from utils import (
    validate_dependencies,
    setup_logging,
    get_pdf_files,
    extract_cards_from_pdf,
    create_extraction_summary,
)


def process_pdf(pdf_info):
    """Wrapper function for parallel processing.
    
    Must be at module level to be picklable for multiprocessing.
    """
    pdf_path, theme_name = pdf_info
    # Use None logger for parallel processing to avoid file conflicts
    # Main process will handle logging
    try:
        extracted_cards = extract_cards_from_pdf(pdf_path, theme_name, None)
        return theme_name, extracted_cards, None
    except Exception as e:
        return theme_name, [], str(e)


def main():
    """Main entry point for card extraction."""
    parser = argparse.ArgumentParser(
        description="Extract card images from tactical theme PDFs"
    )
    parser.add_argument(
        "--pdf-dir",
        type=str,
        default=str(PDF_INPUT_DIR),
        help=f"Directory containing PDF files (default: {PDF_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(CARDS_OUTPUT_DIR),
        help=f"Output directory for extracted cards (default: {CARDS_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output to console (logs still go to file)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Process PDFs in parallel (faster but uses more CPU/memory)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: number of CPU cores)",
    )
    
    args = parser.parse_args()
    
    try:
        # Validate dependencies
        validate_dependencies()
        
        # Set up logging
        logger = setup_logging(verbose=args.verbose and not args.quiet)
        
        logger.info("=" * 60)
        logger.info("CARD IMAGE EXTRACTION STARTED")
        logger.info("=" * 60)
        logger.info("All dependencies validated")
        logger.info(f"PDF input directory: {PDF_INPUT_DIR}")
        logger.info(f"Output directory: {CARDS_OUTPUT_DIR}")
        
        # Get list of PDF files
        pdf_files = get_pdf_files()
        logger.info(f"Found {len(pdf_files)} PDF file(s) to process")
        logger.info("")
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {PDF_INPUT_DIR}")
            return
        
        # Extract cards from each PDF
        extraction_results = {}
        total_cards_extracted = 0
        
        if args.parallel:
            # Parallel processing
            num_workers = args.workers or multiprocessing.cpu_count()
            logger.info(f"Processing {len(pdf_files)} PDF(s) in parallel with {num_workers} worker(s)")
            logger.info("")
            
            with ProcessPoolExecutor(max_workers=num_workers) as executor:
                future_to_pdf = {executor.submit(process_pdf, pdf_info): pdf_info for pdf_info in pdf_files}
                
                for future in as_completed(future_to_pdf):
                    try:
                        theme_name, extracted_cards, error = future.result()
                        if error:
                            logger.error(f"Error processing {theme_name}: {error}")
                        extraction_results[theme_name] = extracted_cards
                        total_cards_extracted += len(extracted_cards)
                        logger.info(f"Completed: {theme_name} ({len(extracted_cards)} cards)")
                    except Exception as e:
                        pdf_info = future_to_pdf[future]
                        logger.error(f"Error processing {pdf_info[1]}: {e}", exc_info=True)
        else:
            # Sequential processing (original behavior)
            for pdf_path, theme_name in pdf_files:
                logger.info(f"--- Processing: {theme_name} ---")
                extracted_cards = extract_cards_from_pdf(pdf_path, theme_name, logger)
                extraction_results[theme_name] = extracted_cards
                total_cards_extracted += len(extracted_cards)
                logger.info(f"Theme '{theme_name}': {len(extracted_cards)} card(s) extracted")
                logger.info("")
        
        # Create summary report
        create_extraction_summary(extraction_results, logger)
        
        # Log final summary
        logger.info("=" * 60)
        logger.info("EXTRACTION COMPLETE")
        logger.info(f"Total cards extracted: {total_cards_extracted}")
        logger.info(f"Output directory: {CARDS_OUTPUT_DIR}")
        logger.info(f"Logs directory: {LOGS_DIR}")
        logger.info("=" * 60)
        
    except ImportError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Please install required dependencies with:", file=sys.stderr)
        print("  pip install PyMuPDF Pillow", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
