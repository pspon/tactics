# Card Image Extraction from Tactical Theme PDFs

This Python project extracts embedded images of playing cards from PDF files organized by tactical chess themes.

## Project Overview

The project processes 7 PDFs, each representing a different tactical theme:
- **Ambush.pdf**
- **Assassination.pdf**
- **Counterattack.pdf**
- **Deflection.pdf**
- **Discovered Attack.pdf**
- **Skewer.pdf**
- **X-ray.pdf**

All images embedded in these PDFs are extracted and saved to the output directory, organized by theme.

## Project Structure

```
Tactician/
├── pdf/                          # Input PDF files
│   ├── Ambush.pdf
│   ├── Assassination.pdf
│   ├── Counterattack.pdf
│   ├── Deflection.pdf
│   ├── Discovered Attack.pdf
│   ├── Skewer.pdf
│   └── X-ray.pdf
├── src/                          # Source code
│   ├── config.py                 # Configuration settings
│   ├── utils.py                  # Utility functions
│   ├── extract_cards.py          # Main extraction script
│   └── extractors/               # Extraction strategies
├── output/                       # Extracted images and metadata
│   ├── cards/                    # Extracted card images (PNG)
│   └── metadata/                 # Extraction reports
├── logs/                         # Log files
├── config/                       # Configuration files
├── requirements.txt              # Python dependencies
└── README.md                     # This file
```

## Installation

### 1. Python Requirements
Ensure you have Python 3.8 or higher installed.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**Note for Windows users:** If you encounter issues with `pdf2image`, you may need to install Poppler separately:
- Download from: https://github.com/oschwartz10612/poppler-windows/releases/
- Or install via package manager if available
- Update Poppler path in Windows PATH environment variable

### 3. Verify Installation

```bash
python -m pip list
```

Ensure these packages are installed:
- PyMuPDF
- pdf2image
- Pillow

## Usage

### Basic Usage

Run the extraction with default settings:

```bash
cd src
python extract_cards.py
```

### Advanced Options

**Verbose output (detailed logging):**
```bash
python extract_cards.py --verbose
```

**Minimal output:**
```bash
python extract_cards.py --quiet
```

**Specify custom PDF directory:**
```bash
python extract_cards.py --pdf-dir "C:\path\to\pdfs"
```

**Specify custom output directory:**
```bash
python extract_cards.py --output-dir "C:\path\to\output"
```

## Output

After running the extraction script, you'll find:

### Extracted Images
- Location: `output/cards/`
- Naming format: `{THEME}_page{PAGE_NUM}_img{IMG_NUM}.png`
- Example: `Ambush_page1_img1.png`, `Assassination_page2_img3.png`

### Extraction Summary
- Location: `output/metadata/extraction_summary.txt`
- Contains: Count and list of all extracted images per theme

### Logs
- Location: `logs/extraction.log`
- Contains: Detailed extraction process information

## Configuration

Edit `src/config.py` to customize:

- `MIN_IMAGE_WIDTH`, `MIN_IMAGE_HEIGHT`: Minimum image dimensions (default: 50x50)
- `IMAGE_FORMAT`: Output format (default: PNG)
- `DPI_FOR_CONVERSION`: DPI for PDF-to-image conversion (default: 150)
- `MAX_WORKERS`: Parallel processing workers (default: 4)
- `VERBOSE`: Enable verbose output (default: True)
- `DEBUG`: Enable debug mode (default: False)

## Extraction Methods

The project uses two extraction methods:

### Primary Method: PyMuPDF
- Fast and efficient
- Extracts images directly from PDF structure
- No need for PDF rendering

### Fallback Method: pdf2image + Pillow
- Used if primary method finds no images
- Converts PDF pages to images
- Useful for PDFs with images embedded differently

## Troubleshooting

### "PyMuPDF not installed" error
```bash
pip install PyMuPDF
```

### "pdf2image not installed" error
```bash
pip install pdf2image
```

### Poppler not found (Windows)
1. Download Poppler from: https://github.com/oschwartz10612/poppler-windows/releases/
2. Extract to a known location
3. Add to Windows PATH or update config.py

### No images extracted
1. Check logs: `logs/extraction.log`
2. Verify PDF files contain embedded images (not scanned pages)
3. Check image size requirements in `config.py`
4. Try with `--verbose` flag for more details

## Performance Tips

- Use PyMuPDF (primary method) for large PDFs - it's faster
- Adjust `DPI_FOR_CONVERSION` in config.py to balance quality and speed
- Use `MIN_IMAGE_WIDTH` and `MIN_IMAGE_HEIGHT` to filter small images

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| PyMuPDF | 1.24.5 | Primary PDF image extraction |
| pdf2image | 1.16.3 | Fallback PDF conversion to images |
| Pillow | 10.1.0 | Image processing and format conversion |
| poppler-utils | 0.1.0 | PDF rendering support |

## License

This project is provided as-is for extracting card images from tactical theme PDFs.

## Author Notes

This extraction tool is specifically designed for the 7 tactical chess themes:
1. **Ambush** - Attacking opponent's pieces in unexpected ways
2. **Assassination** - Targeted attacks on key pieces
3. **Counterattack** - Defensive attacks turning tables
4. **Deflection** - Forcing defender away from key square
5. **Discovered Attack** - Attacking after moving a piece
6. **Skewer** - Forcing piece to move, capturing piece behind
7. **X-ray** - Attacking through pieces on same line

Each PDF contains card images related to its theme for tactical training.
