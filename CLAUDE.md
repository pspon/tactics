# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

Tactician extracts playing card images from tactical chess theme PDFs and serves them through web interfaces. It processes 7 tactical themes (Ambush, Assassination, Counterattack, Deflection, Discovered Attack, Skewer, X-ray). Each card image is a combined PNG (front + back side-by-side) that gets split at display time.

## Commands

**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Extract cards from PDFs:**
```bash
cd src
python extract_cards.py              # Sequential (~5 min)
python extract_cards.py --parallel   # Parallel (~1.5 min)
python extract_cards.py --verbose    # Verbose logging
```

**Run the Streamlit app (primary UI):**
```bash
streamlit run streamlit_app.py
```

**Run the Flask app (alternative UI):**
```bash
python flask_viewer.py
```

**Run tests:**
```bash
python run_tests.py
pytest
```

**Docker:**
```bash
docker build -t tactician .
docker run -p 8501:8501 tactician
```

## Architecture

### Data Flow

```
pdf/*.pdf
  → src/extract_cards.py (PyMuPDF primary, pdf2image fallback)
  → output/cards/*.png (combined front+back images)
  → static/cards/front/*.png + static/cards/back/*.png (split at runtime)
```

### Key Modules

- **`src/config.py`** — Central config: input/output paths, DPI, image format, theme name mapping. Auto-creates output dirs on import.
- **`src/utils.py`** — Extraction utilities: PDF discovery, PyMuPDF/pdf2image extraction, logging setup, theme page-range config (hardcoded to skip cover/credit pages).
- **`src/extract_cards.py`** — Main extraction script. Uses `ProcessPoolExecutor` with a module-level `process_pdf()` wrapper (required for pickling in multiprocessing).
- **`src/web_utils.py`** — Shared web layer: card discovery with mtime-based caching, LRU-cached image loading (128 slots), SHA256 user auth, deck persistence to JSON.

### Web Apps

**`streamlit_app.py`** (primary) — On first start, `@st.cache_resource` splits all `output/cards/*.png` into `static/cards/front/` and `static/cards/back/`. Builds a full HTML board with injected card data and JavaScript for drag/flip/filter. Layout state lives in browser localStorage, not server state.

**`flask_viewer.py`** (alternative) — Serves card halves via `/card/<side>/<filename>` with 256-slot LRU cache returning raw bytes. Supports server-side layout persistence via `layouts/` directory (JSON files).

### Storage (all local, no database)

| Location | Contents |
|---|---|
| `output/cards/` | Extracted PNG card images |
| `output/metadata/users.json` | SHA256-hashed user accounts |
| `output/metadata/decks/` | User deck files (`{user}__{deck}.json`) |
| `output/metadata/card_names.json` | Display name overrides |
| `output/metadata/card_types.json` | Card type metadata |
| `layouts/` | Flask-saved board layouts |
| `static/cards/front/` | Pre-split front halves (Streamlit) |
| `static/cards/back/` | Pre-split back halves (Streamlit) |

### Caching Layers

`web_utils.py` uses two strategies: file mtime comparison (card discovery, users file) and `functools.lru_cache` (images: 128 slots, decks: 64 slots, metadata: 1 slot each). Call `clear_caches()` to invalidate all. Flask adds its own 256-slot LRU for card image bytes.
