#!/usr/bin/env python3
"""
Create a template card types JSON file for manual editing.

This creates a card_types.json file with all cards set to "Unknown".
Edit the file manually to assign appropriate types to each card.
"""

import json
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from web_utils import CARDS_DIR, META_DIR

TYPES_FILE = META_DIR / "card_types.json"


def create_template_types():
    """Create template types file with all cards as Unknown."""
    # Ensure directories exist
    META_DIR.mkdir(parents=True, exist_ok=True)

    # Get all card files
    card_files = []
    if CARDS_DIR.exists():
        card_files = [f for f in CARDS_DIR.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg'}]
    else:
        print(f"Cards directory not found: {CARDS_DIR}")
        return

    if not card_files:
        print("No card images found.")
        return

    # Create template with all Unknown
    types = {}
    for card_file in sorted(card_files):
        types[card_file.name] = "Unknown"

    # Save to JSON
    with open(TYPES_FILE, 'w', encoding='utf-8') as f:
        json.dump(types, f, indent=2, ensure_ascii=False)

    print(f"Template created: {TYPES_FILE}")
    print(f"Edit this file to assign types like 'Recipe', 'Technique', etc. to each card.")
    print(f"Format: {{\"card_filename.png\": \"Type\", ...}}")


def main():
    """Main function."""
    print("Card Types Template Creator")
    print("=" * 30)
    create_template_types()


if __name__ == "__main__":
    main()
