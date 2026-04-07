import sys
from pathlib import Path

# Ensure project root is on sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.utils import validate_dependencies, setup_logging, extract_cards_from_pdf

PDF_PATH = str(project_root / 'pdf' / 'Productivity_Tactics.pdf')
THEME = 'Productivity_Tactics'

if __name__ == '__main__':
    validate_dependencies()
    logger = setup_logging(verbose=True)
    logger.info(f"Running smoke test for {PDF_PATH}")
    results = extract_cards_from_pdf(PDF_PATH, THEME, logger)
    logger.info(f"Smoke test finished. Extracted {len(results)} cards.")
    for p, n in results[:10]:
        logger.info(f"  - {n}")
