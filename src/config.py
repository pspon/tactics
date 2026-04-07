"""
Configuration settings for card extraction project.
"""

from pathlib import Path

# Project directories
PROJECT_ROOT = Path(__file__).parent.parent
PDF_INPUT_DIR = PROJECT_ROOT / "pdf"
CARDS_OUTPUT_DIR = PROJECT_ROOT / "output" / "cards"
LOGS_DIR = PROJECT_ROOT / "logs"

# Image extraction settings
DPI_FOR_CONVERSION = 150  # DPI for PDF to image conversion
IMAGE_FORMAT = "PNG"  # Output image format
IMAGE_QUALITY = 95  # Quality for JPEG (not used for PNG)

# Create directories if they don't exist
CARDS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Tactical theme mapping
TACTICAL_THEMES = {
    "Idea_Tactics": "Idea Tactics",
    "Productivity_Tactics": "Productivity Tactics",
    "Retrospective_Tactics": "Retrospective Tactics",
    "Storyteller_Tactics": "Storyteller Tactics",
    "Strategy_Tactics": "Strategy Tactics",
    "Team_Tactics": "Team Tactics",
    "Workshop_Tactics": "Workshop Tactics",
}
