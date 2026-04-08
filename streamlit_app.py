"""
Tactician - Card Navigator
Streamlit entry point that serves the Miro-like card board.

Card images are loaded from output/cards/ at startup.  They can be provided
in two ways (checked in this order):

  1. Volume mount / local extraction
       Already present in output/cards/ – nothing extra needed.

  2. Private GitHub repository  (recommended for Streamlit Cloud)
       Set CARDS_GITHUB_TOKEN and CARDS_REPO in .streamlit/secrets.toml
       (or as environment variables).  The app clones the repo once per
       server session and copies the images into output/cards/.

Expected private repo layout:
    cards/        ← PNG card images  → output/cards/
    metadata/     ← optional JSON    → output/metadata/  (users.json skipped)

After loading, card images are split into front/back once and served via
Streamlit's static file serving from static/cards/{front,back}/.
Layouts are persisted in the browser via localStorage (no server required).

Run:  streamlit run streamlit_app.py
"""

import base64
import html as html_module
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

from src.web_utils import (
    discover_cards,
    ensure_metadata_dirs,
    login_user,
    signup_user,
)

_APP_DIR = Path(__file__).parent
CARDS_DIR = _APP_DIR / "output" / "cards"
STATIC_FRONT = _APP_DIR / "static" / "cards" / "front"
STATIC_BACK = _APP_DIR / "static" / "cards" / "back"


def _read_secret(key: str) -> str:
    """Return a value from st.secrets, falling back to env var, or ''."""
    try:
        return str(st.secrets.get(key, "") or "")
    except Exception:
        return os.environ.get(key, "")


@st.cache_resource(show_spinner="Fetching card library…")
def fetch_card_library() -> int:
    """Clone the private cards repo if card images are not already on disk.

    Skips the fetch when output/cards/ is already populated (volume mount or
    previous run).  Returns the number of card images available afterwards.

    Secrets / env vars used:
        CARDS_GITHUB_TOKEN  – GitHub personal access token (repo read scope)
        CARDS_REPO          – repo in "owner/name" form, e.g. "alice/tactician-cards"
    """
    # Check if cards already present (volume mount, prior fetch, local extraction)
    existing = [
        p for p in CARDS_DIR.glob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    if existing:
        return len(existing)

    token = _read_secret("CARDS_GITHUB_TOKEN")
    repo  = _read_secret("CARDS_REPO")

    if not token or not repo:
        return 0  # No config supplied; caller will surface a helpful message

    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    # Build authenticated clone URL; token never appears in error messages
    clone_url = f"https://x-access-token:{token}@github.com/{repo}.git"

    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--quiet", clone_url, tmp],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Could not fetch card library from '{repo}'. "
                "Verify CARDS_GITHUB_TOKEN and CARDS_REPO in your secrets."
            )

        tmp_path = Path(tmp)

        # ---- cards -------------------------------------------------------
        src_cards = tmp_path / "cards"
        if src_cards.exists():
            shutil.copytree(src_cards, CARDS_DIR, dirs_exist_ok=True)
        else:
            # Fallback: images sit at the repo root
            for img in tmp_path.iterdir():
                if img.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    shutil.copy2(img, CARDS_DIR / img.name)

        # ---- metadata (optional) -----------------------------------------
        src_meta = tmp_path / "metadata"
        if src_meta.exists():
            meta_dir = _APP_DIR / "output" / "metadata"
            meta_dir.mkdir(parents=True, exist_ok=True)
            for item in src_meta.iterdir():
                # Never overwrite runtime credentials from the private repo
                if item.name in {"users.json", "decks"}:
                    continue
                dest = meta_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)

    images = [
        p for p in CARDS_DIR.glob("*")
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    ]
    return len(images)


def prepare_card_images() -> int:
    """Split each combined card image into separate front and back PNGs.

    Runs on every authenticated page load, but skips cards whose split
    images already exist, so it is fast after the first run.  Not cached
    with @st.cache_resource so that missing static files (e.g. after a
    volume-mount or ephemeral-filesystem event) are always recovered.
    Returns the number of newly processed cards.
    """
    STATIC_FRONT.mkdir(parents=True, exist_ok=True)
    STATIC_BACK.mkdir(parents=True, exist_ok=True)
    (_APP_DIR / "layouts").mkdir(parents=True, exist_ok=True)

    if not CARDS_DIR.exists():
        return 0

    count = 0
    for card_path in sorted(CARDS_DIR.iterdir()):
        if card_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            continue
        front_out = STATIC_FRONT / card_path.name
        back_out = STATIC_BACK / card_path.name
        if front_out.exists() and back_out.exists():
            continue
        img = Image.open(card_path).convert("RGB")
        w, h = img.size
        mid = w // 2
        img.crop((0, 0, mid, h)).save(front_out, format="PNG")
        img.crop((mid, 0, w, h)).save(back_out, format="PNG")
        count += 1
    return count


def _e(text: str) -> str:
    """HTML-escape a value for safe embedding in attributes or text."""
    return html_module.escape(str(text))


@st.cache_data(show_spinner=False)
def _card_img_b64(filename: str) -> tuple:
    """Return (front_data_uri, back_data_uri) for *filename*.

    Reads the pre-split images produced by prepare_card_images() and
    encodes them as PNG data URIs.  The board HTML is then fully
    self-contained and does not depend on Streamlit's /app/static/ route,
    which can fail inside a sandboxed components.html() iframe on
    Streamlit Cloud.  Results are cached per filename for the lifetime
    of the server process.
    """
    def _to_uri(path: Path) -> str:
        if not path.exists():
            return ""
        with open(path, "rb") as fh:
            return "data:image/png;base64," + base64.b64encode(fh.read()).decode()

    return _to_uri(STATIC_FRONT / filename), _to_uri(STATIC_BACK / filename)


def build_board_html(cards: list, themes: list) -> str:
    """Return the full board HTML with card data and themes injected."""

    # --- Sidebar deck-tree entries ---
    deck_tree_html = ""
    for theme in themes:
        deck_tree_html += f"""
        <div class="deck">
          <div class="deck-header">
            <input type="checkbox" class="theme-checkbox">
            <h4>{_e(theme)}</h4>
          </div>
          <div class="deck-cards" style="padding-left:12px;display:none;"></div>
        </div>"""

    # --- Board card elements ---
    board_cards_html = ""
    for i, card in enumerate(cards):
        left = (i % 8) * 545
        top = (i // 8) * 883
        front_src, back_src = _card_img_b64(card['filename'])
        board_cards_html += f"""
        <div class="card"
             data-deck="{_e(card['theme'])}"
             data-filename="{_e(card['filename'])}"
             data-type="{_e(card.get('type', 'Unknown'))}"
             data-back-src="{back_src}"
             style="left:{left}px;top:{top}px;">
          <div class="card-image-wrapper">
            <img src="{front_src}">
          </div>
          <div class="card-meta"><strong>{_e(card['name'])}</strong></div>
        </div>"""

    # NOTE: curly braces in the JS/CSS block are doubled {{ }} to escape Python's
    # f-string interpolation.
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Card Navigator</title>
<style>
:root {{
  --bg-color: #f4f4f9;
  --dot-color: #d1d1d6;
  --primary: #2b6cb0;
  --selection-stroke: #2b6cb0;
  --selection-fill: rgba(43,108,176,0.1);
}}
html,body {{ margin:0; height:100%; overflow:hidden; font-family:'Inter',system-ui,sans-serif; background-color:var(--bg-color); }}

/* SIDEBAR */
#sidebar {{ position:fixed; left:0; top:0; bottom:0; width:240px; background:white; box-shadow:2px 0 10px rgba(0,0,0,0.1); padding:16px; overflow-y:auto; transition:transform 0.3s ease; z-index:200; padding-top:60px; }}
#sidebar.collapsed {{ transform:translateX(-100%); }}
#sidebar h3 {{ margin-top:0; font-size:16px; margin-bottom:8px; }}
#sidebar h4 {{ margin-top:0; margin-left:10px; font-size:14px; margin-bottom:4px; display:inline-block; cursor:pointer; }}
#sidebar-toggle {{ position:fixed; left:0; top:16px; z-index:300; background:var(--primary); color:white; border:none; padding:6px 12px; border-radius:0 4px 4px 0; cursor:pointer; }}
#sidebar input[type="text"] {{ width:90%; padding:6px 8px; border-radius:4px; border:1px solid #ccc; margin-bottom:12px; }}
#sidebar label {{ display:block; margin-bottom:6px; cursor:pointer; }}
#sidebar input[type="checkbox"] {{ margin-right:6px; }}
.deck-header {{ font-weight:bold; cursor:pointer; margin-top:8px; display:flex; align-items:center; gap:4px; }}
.deck-header h4 {{ margin:0; line-height:1.2; }}
.deck-header input[type="checkbox"] {{ margin:0; flex-shrink:0; }}
.deck-cards label {{ display:block; margin-bottom:4px; cursor:pointer; font-size:13px; }}

/* UI DOCK */
#ui-dock {{ position:fixed; bottom:24px; left:50%; transform:translateX(-50%); background:white; padding:8px 16px; display:flex; gap:12px; z-index:100; border-radius:12px; box-shadow:0 4px 20px rgba(0,0,0,0.15); align-items:center; }}
button {{ background:white; border:1px solid #ddd; padding:6px 12px; border-radius:6px; cursor:pointer; font-weight:500; transition:background 0.1s; }}
button:hover {{ background:#f9f9f9; }} button:active {{ background:#eee; }}

/* CANVAS */
#viewport {{ position:absolute; inset:0; cursor:default; background-image:radial-gradient(var(--dot-color) 1px, transparent 1px); background-size:24px 24px; }}
#viewport.panning {{ cursor:grabbing; }}
#board {{ position:absolute; top:0; left:0; transform-origin:0 0; will-change:transform; }}

/* CARDS */
.card {{ position:absolute; width:525px; height:863px; background:white; border:1px solid #ddd; border-radius:8px; cursor:grab; user-select:none; box-shadow:0 2px 5px rgba(0,0,0,0.05); transition:box-shadow 0.2s, outline 0.1s; overflow:hidden; display:flex; flex-direction:column; }}
.card:hover {{ box-shadow:0 5px 15px rgba(0,0,0,0.1); }}
.card.selected {{ outline:2px solid var(--primary); box-shadow:0 0 0 4px rgba(43,108,176,0.2); z-index:10; }}
.card.hidden {{ display:none; pointer-events:none; }}
.card-image-wrapper {{ width:100%; height:100%; background:#eee; display:flex; align-items:center; justify-content:center; overflow:hidden; }}
.card img {{ width:100%; height:100%; object-fit:cover; pointer-events:none; }}
.card-meta {{ padding:10px; font-size:12px; color:#555; background:white; border-top:1px solid #eee; display:none; }}
.show-names .card-meta {{ display:block; }}

/* SELECTION BOX */
#selection-box {{ position:absolute; background:var(--selection-fill); border:1px solid var(--selection-stroke); display:none; pointer-events:none; z-index:999; }}

/* OVERLAY */
#overlay {{ position:fixed; inset:0; background:rgba(0,0,0,0.7); display:none; align-items:center; justify-content:center; z-index:1000; backdrop-filter:blur(4px); }}
#overlay img {{ max-width:90%; max-height:90%; border-radius:4px; box-shadow:0 20px 60px rgba(0,0,0,0.5); }}
</style>
</head>
<body>

<!-- SIDEBAR -->
<button id="sidebar-toggle">☰ Filters</button>
<div id="sidebar" class="collapsed">
  <h3>Search Cards</h3>
  <input type="text" id="cardSearch" placeholder="Type card name…"/>
  <h3>Decks</h3>
  <div id="deckTree">{deck_tree_html}</div>
</div>

<!-- UI DOCK -->
<div id="ui-dock">
  <button id="btn-gather">Gather</button>
  <button id="btn-flip">Flip</button>
  <button id="btn-reset">Reset View</button>
  <button id="btn-toggle-names">Toggle Names</button>
  <button id="btn-hide-selected">Hide Selected</button>
  <button id="btn-snap-grid">Snap to Grid</button>
  <button id="btn-save-layout">Save Layout</button>
  <select id="layout-select" style="margin-left:12px;"><option value="">Load Layout…</option></select>
  <button id="btn-delete-layout">Delete Layout</button>
</div>

<!-- BOARD -->
<div id="viewport">
  <div id="board">{board_cards_html}</div>
</div>

<div id="selection-box"></div>
<div id="overlay"><img/></div>

<script>
/* ---- STATE ---- */
const viewport = document.getElementById('viewport');
const board    = document.getElementById('board');
let cards = [...document.querySelectorAll('.card')];
let scale = 0.3, panX = 0, panY = 0;
let isPanning = false, isSpacePressed = false, panStartX = 0, panStartY = 0;
let showNames = false, isSelecting = false, selectStartX = 0, selectStartY = 0;

/* ---- SIDEBAR TOGGLE ---- */
const sidebar = document.getElementById('sidebar');
document.getElementById('sidebar-toggle').addEventListener('click', () => {{
  sidebar.classList.toggle('collapsed');
}});

/* ---- FILTER ---- */
function filterCards() {{
  const q = document.getElementById('cardSearch').value.toLowerCase();
  cards.forEach(card => {{
    const name = card.querySelector('.card-meta strong').textContent.toLowerCase();
    card.classList.toggle('hidden', !name.includes(q));
  }});
  updateDeckTree();
}}
document.getElementById('cardSearch').addEventListener('input', filterCards);

/* ---- DECK TREE ---- */
const deckTree = document.getElementById('deckTree');

function updateDeckTree() {{
  document.querySelectorAll('.deck-cards').forEach(dc => dc.innerHTML = '');
  const decks = [...new Set(cards.map(c => c.dataset.deck))];
  decks.forEach(deck => {{
    const container = [...deckTree.querySelectorAll('.deck')].find(
      d => d.querySelector('h4').textContent === deck
    );
    if (!container) return;
    const cardContainer  = container.querySelector('.deck-cards');
    const themeCheckbox  = container.querySelector('.theme-checkbox');
    const deckCards      = cards.filter(c => c.dataset.deck === deck);

    // Group by type
    const types = {{}};
    deckCards.forEach(card => {{
      const type = card.dataset.type || 'Unknown';
      if (!types[type]) types[type] = [];
      types[type].push(card);
    }});

    Object.keys(types).forEach(type => {{
      const typeCards = types[type];
      const typeDiv   = document.createElement('div');
      typeDiv.className = 'type-container';
      typeDiv.style.marginLeft = '10px';

      const typeHeader = document.createElement('div');
      typeHeader.className = 'type-header';
      typeHeader.style.cssText = 'display:flex;align-items:center;gap:4px;margin-top:4px;cursor:pointer;';

      const typeCheckbox = document.createElement('input');
      typeCheckbox.type = 'checkbox';
      typeCheckbox.className = 'type-checkbox';

      const typeLabel = document.createElement('h5');
      typeLabel.textContent = type;
      typeLabel.style.cssText = 'margin:0;font-size:13px;';

      typeHeader.appendChild(typeCheckbox);
      typeHeader.appendChild(typeLabel);
      typeDiv.appendChild(typeHeader);

      const typeCardContainer = document.createElement('div');
      typeCardContainer.className = 'type-cards';
      typeCardContainer.style.cssText = 'padding-left:12px;display:none;';

      typeCards.forEach(card => {{
        const label = document.createElement('label');
        const cb    = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !card.classList.contains('hidden');
        cb.addEventListener('change', () => {{
          card.classList.toggle('hidden', !cb.checked);
          updateTypeCheckbox(typeCheckbox, typeCardContainer);
          updateThemeCheckbox(themeCheckbox, cardContainer);
        }});
        label.appendChild(cb);
        label.append(' ' + card.querySelector('.card-meta strong').textContent);
        label.dataset.filename = card.dataset.filename;
        typeCardContainer.appendChild(label);
      }});

      typeDiv.appendChild(typeCardContainer);
      cardContainer.appendChild(typeDiv);

      typeCheckbox.addEventListener('change', () => {{
        typeCards.forEach((c, i) => {{
          const cb = typeCardContainer.querySelectorAll('input[type="checkbox"]')[i];
          cb.checked = typeCheckbox.checked;
          c.classList.toggle('hidden', !cb.checked);
        }});
        updateTypeCheckbox(typeCheckbox, typeCardContainer);
        updateThemeCheckbox(themeCheckbox, cardContainer);
      }});

      typeHeader.addEventListener('click', e => {{
        if (e.target === typeCheckbox) return;
        typeCardContainer.style.display =
          typeCardContainer.style.display === 'none' ? 'block' : 'none';
      }});

      updateTypeCheckbox(typeCheckbox, typeCardContainer);
    }});

    themeCheckbox.addEventListener('change', () => {{
      cardContainer.querySelectorAll('.type-checkbox').forEach(tc => {{
        tc.checked = themeCheckbox.checked;
        const tDiv = tc.closest('.type-container');
        const tCC  = tDiv.querySelector('.type-cards');
        tCC.querySelectorAll('input[type="checkbox"]').forEach(cb => {{
          cb.checked = tc.checked;
          const card = cards.find(c => c.dataset.filename === cb.parentElement.dataset.filename);
          if (card) card.classList.toggle('hidden', !tc.checked);
        }});
        updateTypeCheckbox(tc, tCC);
      }});
      updateThemeCheckbox(themeCheckbox, cardContainer);
    }});

    updateThemeCheckbox(themeCheckbox, cardContainer);
  }});

  document.querySelectorAll('.deck-header h4').forEach(header => {{
    if (header.classList.contains('js-bound')) return;
    header.addEventListener('click', () => {{
      const cardList = header.parentElement.nextElementSibling;
      cardList.style.display = cardList.style.display === 'none' ? 'block' : 'none';
    }});
    header.classList.add('js-bound');
  }});
}}

function updateThemeCheckbox(cb, container) {{
  const all = [...container.querySelectorAll('input[type="checkbox"]')];
  const n   = all.filter(c => c.checked).length;
  cb.checked       = n > 0;
  cb.indeterminate = n > 0 && n < all.length;
}}

function updateTypeCheckbox(cb, container) {{
  const all = [...container.querySelectorAll('input[type="checkbox"]')];
  const n   = all.filter(c => c.checked).length;
  cb.checked       = n > 0;
  cb.indeterminate = n > 0 && n < all.length;
}}

/* ---- VIEWPORT ---- */
function updateView() {{
  board.style.transform = `translate(${{panX}}px,${{panY}}px) scale(${{scale}})`;
  viewport.style.backgroundPosition = `${{panX}}px ${{panY}}px`;
  viewport.style.backgroundSize = `${{24 * scale}}px ${{24 * scale}}px`;
}}
window.addEventListener('keydown', e => {{
  if (e.code === 'Space' && !isSpacePressed) {{
    isSpacePressed = true; viewport.style.cursor = 'grab'; e.preventDefault();
  }}
}});
window.addEventListener('keyup', e => {{
  if (e.code === 'Space') {{ isSpacePressed = false; viewport.style.cursor = 'default'; isPanning = false; }}
}});

/* ---- CARD DRAG ---- */
const cardWidth = 525, cardHeight = 863, marginX = 20, marginY = 20;
const spacingX  = cardWidth + marginX, spacingY = cardHeight + marginY;
function getPos(el) {{ return {{ left: parseFloat(el.style.left) || 0, top: parseFloat(el.style.top) || 0 }}; }}

let isDraggingCards = false;
cards.forEach(card => {{
  card.addEventListener('mousedown', e => {{
    if (isSpacePressed || e.button !== 0) return;
    e.stopPropagation();
    const isSelected = card.classList.contains('selected');
    if (e.shiftKey) card.classList.toggle('selected');
    else if (!isSelected) {{ deselectAll(); card.classList.add('selected'); }}
    isDraggingCards = true;
    const mx0 = e.clientX, my0 = e.clientY;
    const selected  = document.querySelectorAll('.card.selected');
    const initPos   = Array.from(selected).map(c => ({{ el: c, ...getPos(c) }}));
    function moveCards(ev) {{
      const dx = (ev.clientX - mx0) / scale, dy = (ev.clientY - my0) / scale;
      initPos.forEach(p => {{ p.el.style.left = (p.left + dx) + 'px'; p.el.style.top = (p.top + dy) + 'px'; }});
    }}
    function stopDrag() {{
      window.removeEventListener('mousemove', moveCards);
      window.removeEventListener('mouseup', stopDrag);
      isDraggingCards = false;
    }}
    window.addEventListener('mousemove', moveCards);
    window.addEventListener('mouseup', stopDrag);
  }});
  card.addEventListener('dblclick', e => {{ e.stopPropagation(); openOverlay(card); }});
}});

function deselectAll() {{ cards.forEach(c => c.classList.remove('selected')); }}
function openOverlay(card) {{
  const overlay = document.getElementById('overlay');
  overlay.querySelector('img').src = card.querySelector('img').src;
  overlay.style.display = 'flex';
  overlay.dataset.cardId = card.dataset.filename;
}}

/* ---- PAN & SELECTION BOX ---- */
viewport.addEventListener('mousedown', e => {{
  if (e.button === 1 || (isSpacePressed && e.button === 0)) {{
    isPanning = true; panStartX = e.clientX - panX; panStartY = e.clientY - panY;
    viewport.classList.add('panning'); e.preventDefault(); return;
  }}
  if (e.target === viewport || e.target === board) {{
    deselectAll();
    isSelecting = true;
    selectStartX = (e.clientX - panX) / scale;
    selectStartY = (e.clientY - panY) / scale;
    const box = document.getElementById('selection-box');
    box.style.cssText = `display:block;left:${{e.clientX}}px;top:${{e.clientY}}px;width:0;height:0;`;
  }}
}});
viewport.addEventListener('mousemove', e => {{
  if (isPanning) {{ panX = e.clientX - panStartX; panY = e.clientY - panStartY; updateView(); return; }}
  if (isSelecting) {{
    const cx = (e.clientX - panX) / scale, cy = (e.clientY - panY) / scale;
    const left   = Math.min(selectStartX, cx) * scale + panX;
    const top    = Math.min(selectStartY, cy) * scale + panY;
    const width  = Math.abs(cx - selectStartX) * scale;
    const height = Math.abs(cy - selectStartY) * scale;
    const box = document.getElementById('selection-box');
    box.style.cssText = `display:block;left:${{left}}px;top:${{top}}px;width:${{width}}px;height:${{height}}px;`;
    const rect = {{ left: Math.min(selectStartX, cx), top: Math.min(selectStartY, cy), right: Math.max(selectStartX, cx), bottom: Math.max(selectStartY, cy) }};
    cards.forEach(card => {{
      if (card.classList.contains('hidden')) return;
      const p = getPos(card);
      const cr = {{ left: p.left, top: p.top, right: p.left + cardWidth, bottom: p.top + cardHeight }};
      card.classList.toggle('selected', !(cr.left > rect.right || cr.right < rect.left || cr.top > rect.bottom || cr.bottom < rect.top));
    }});
  }}
}});
window.addEventListener('mouseup', e => {{
  if (isPanning)   {{ isPanning   = false; viewport.classList.remove('panning'); }}
  if (isSelecting) {{ isSelecting = false; document.getElementById('selection-box').style.display = 'none'; }}
}});
viewport.addEventListener('wheel', e => {{
  e.preventDefault();
  const wheel = e.deltaY < 0 ? 1 : -1;
  const zoom  = Math.exp(wheel * 0.1);
  const rect  = viewport.getBoundingClientRect();
  const mx    = e.clientX - rect.left, my = e.clientY - rect.top;
  const wx    = (mx - panX) / scale,   wy = (my - panY) / scale;
  scale = Math.min(Math.max(0.1, scale * zoom), 5);
  panX  = mx - wx * scale; panY = my - wy * scale;
  updateView();
}}, {{ passive: false }});

/* ---- UI ACTIONS ---- */
document.getElementById('btn-gather').onclick = () => {{
  let toGather = cards.filter(c => c.classList.contains('selected'));
  if (!toGather.length) toGather = cards.filter(c => !c.classList.contains('hidden'));
  if (!toGather.length) return;
  toGather.sort((a, b) => {{
    const pa = getPos(a), pb = getPos(b);
    return pa.top !== pb.top ? pa.top - pb.top : pa.left - pb.left;
  }});
  const cols = Math.ceil(Math.sqrt(toGather.length));
  toGather.forEach((c, i) => {{
    c.style.left = (i % cols) * spacingX + 'px';
    c.style.top  = Math.floor(i / cols) * spacingY + 'px';
  }});
  updateDeckTree();
}};

document.getElementById('btn-flip').onclick           = () => flipSelectedCards();
document.getElementById('btn-toggle-names').onclick   = () => {{ showNames = !showNames; document.body.classList.toggle('show-names', showNames); updateDeckTree(); }};
document.getElementById('btn-hide-selected').onclick  = () => hideSelectedCards();
document.getElementById('btn-snap-grid').onclick      = () => snapToGrid();
document.getElementById('overlay').onclick            = () => {{ document.getElementById('overlay').style.display = 'none'; }};

document.getElementById('btn-reset').onclick = () => {{
  cards.forEach(card => card.classList.remove('hidden'));
  cards.forEach((card, i) => {{
    card.style.left = (i % 8 * 545) + 'px';
    card.style.top  = Math.floor(i / 8) * 883 + 'px';
  }});
  panX = 0; panY = 0; scale = 0.3; updateView(); updateDeckTree();
}};

window.addEventListener('keydown', e => {{
  const overlay = document.getElementById('overlay');
  if (overlay.style.display === 'flex' && (e.code === 'ArrowLeft' || e.code === 'ArrowRight')) {{
    e.preventDefault(); flipSelectedCards(true);
  }} else if (e.code === 'Escape') {{
    overlay.style.display = 'none';
  }} else if (e.code === 'Delete') {{
    hideSelectedCards();
  }}
}});

/* ---- FLIP / HIDE / SNAP ---- */
/* Cache the original front src the first time a card is touched. */
function getFrontSrc(card) {{
  if (!card.dataset.frontSrc) card.dataset.frontSrc = card.querySelector('img').src;
  return card.dataset.frontSrc;
}}

function flipSelectedCards(isOverlay = false) {{
  let selected = [...document.querySelectorAll('.card.selected')];
  if (isOverlay) {{
    const cardId = document.getElementById('overlay').dataset.cardId;
    selected = cards.filter(c => c.dataset.filename === cardId);
  }}
  selected.forEach(card => {{
    const img = card.querySelector('img');
    const isFlipped = img.src !== getFrontSrc(card);
    img.src = isFlipped ? getFrontSrc(card) : card.dataset.backSrc;
    if (isOverlay) document.getElementById('overlay').querySelector('img').src = img.src;
  }});
}}

function hideSelectedCards() {{
  document.querySelectorAll('.card.selected').forEach(c => {{
    c.classList.add('hidden'); c.classList.remove('selected');
  }});
  updateDeckTree();
}}

function snapToGrid() {{
  cards.filter(c => !c.classList.contains('hidden')).forEach(card => {{
    const pos = getPos(card);
    card.style.left = Math.round(pos.left / spacingX) * spacingX + 'px';
    card.style.top  = Math.round(pos.top  / spacingY) * spacingY + 'px';
  }});
  updateDeckTree();
}}

/* ---- LAYOUT SAVE / LOAD  (localStorage — no server needed) ---- */
const STORAGE_KEY = 'tactician_layouts';

function getStoredLayouts() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{}}'); }}
  catch(e) {{ return {{}}; }}
}}

function getCurrentLayout() {{
  return {{
    cards: cards.map(card => {{
      const pos = getPos(card);
      return {{
        filename : card.dataset.filename,
        left     : pos.left,
        top      : pos.top,
        hidden   : card.classList.contains('hidden'),
        flipped  : card.querySelector('img').src !== getFrontSrc(card)
      }};
    }}),
    view: {{ panX, panY, scale }}
  }};
}}

function applyLayout(layout) {{
  cards.forEach(c => {{
    c.classList.remove('hidden');
    c.querySelector('img').src = getFrontSrc(c);
  }});
  layout.cards.forEach(d => {{
    const card = cards.find(c => c.dataset.filename === d.filename);
    if (!card) return;
    card.style.left = d.left + 'px';
    card.style.top  = d.top  + 'px';
    if (d.hidden)  card.classList.add('hidden');
    if (d.flipped) card.querySelector('img').src = card.dataset.backSrc;
  }});
  panX = layout.view.panX; panY = layout.view.panY; scale = layout.view.scale;
  updateView();
}}

function loadLayoutList() {{
  const layouts = getStoredLayouts();
  const select  = document.getElementById('layout-select');
  select.innerHTML = '<option value="">Load Layout…</option>';
  Object.keys(layouts).sort().forEach(name => {{
    const opt = document.createElement('option');
    opt.value = name; opt.textContent = name;
    select.appendChild(opt);
  }});
}}

document.getElementById('btn-save-layout').onclick = () => {{
  const name = prompt('Enter layout name:');
  if (!name) return;
  const layouts = getStoredLayouts();
  layouts[name] = getCurrentLayout();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(layouts));
  loadLayoutList();
}};

document.getElementById('layout-select').onchange = function() {{
  const name = this.value;
  if (!name) return;
  const layout = getStoredLayouts()[name];
  if (layout) {{ applyLayout(layout); updateDeckTree(); }}
}};

document.getElementById('btn-delete-layout').onclick = () => {{
  const name = document.getElementById('layout-select').value;
  if (!name) return;
  if (!confirm('Delete layout "' + name + '"?')) return;
  const layouts = getStoredLayouts();
  delete layouts[name];
  localStorage.setItem(STORAGE_KEY, JSON.stringify(layouts));
  loadLayoutList();
}};

/* ---- INIT ---- */
updateView(); filterCards(); updateDeckTree(); loadLayoutList();
</script>
</body>
</html>"""


def _get_allowed_users() -> Optional[List[str]]:
    """Return the configured username allowlist, or None for open access.

    Priority order:
      1. st.secrets["allowed_users"]  – TOML array or comma-separated string
      2. ALLOWED_USERS env var         – comma-separated string (Docker / Flask)

    Returns None when neither is set, meaning no restriction is enforced.
    """
    try:
        val = st.secrets.get("allowed_users", None)
        if val is not None:
            if isinstance(val, str):
                return [u.strip() for u in val.split(",") if u.strip()]
            return [str(u) for u in val]  # TOML array
    except Exception:
        pass
    raw = os.environ.get("ALLOWED_USERS", "").strip()
    if raw:
        return [u.strip() for u in raw.split(",") if u.strip()]
    return None


def show_auth_page(allowed_users: Optional[List[str]]) -> None:
    """Render the login / sign-up page. Sets session state on success."""
    st.markdown(
        """
        <style>
        [data-testid="stVerticalBlock"] > div:first-child { max-width: 420px; margin: 60px auto 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title("Tactician – Card Navigator")

    restricted = allowed_users is not None
    if restricted:
        st.caption("Access is restricted to authorised users.")
    else:
        st.caption("Sign in or create an account to access the card board.")
    tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            if not username:
                st.error("Please enter a username.")
            else:
                ok, msg = login_user(username, password, allowed_users)
                if ok:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error(f"Login failed: {msg}")

    with tab_signup:
        with st.form("signup_form"):
            new_user = st.text_input("Choose a username")
            new_pass = st.text_input("Choose a password (min 8 characters)", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            if not new_user:
                st.error("Username cannot be empty.")
            else:
                ok, msg = signup_user(new_user, new_pass, allowed_users)
                if ok:
                    st.success("Account created! Switch to the Login tab to sign in.")
                else:
                    st.error(f"Registration failed: {msg}")


def main():
    st.set_page_config(
        page_title="Tactician – Card Navigator",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    # Ensure users.json and metadata dirs exist before any auth call
    ensure_metadata_dirs()

    # Resolve allowlist once per page load (cheap read from secrets / env)
    allowed_users = _get_allowed_users()

    # ---- Authentication gate ----
    if not st.session_state.get("logged_in"):
        show_auth_page(allowed_users)
        return

    # ---- Authenticated view ----

    # Minimal top bar: username + logout (no Streamlit chrome below it)
    st.markdown(
        """
        <style>
        #MainMenu, header, footer { visibility: hidden; }
        div[data-testid="stToolbar"] { visibility: hidden; }
        /* Tighten default padding so board sits flush */
        .stApp > section > div { padding-top: 0 !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col_user, col_logout = st.columns([11, 1])
    with col_user:
        st.markdown(
            f"<small style='color:#555;'>Logged in as <strong>{_e(st.session_state.username)}</strong></small>",
            unsafe_allow_html=True,
        )
    with col_logout:
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = None
            st.rerun()

    # Fetch from private repo if output/cards/ is empty (cached per session)
    n_fetched = fetch_card_library()

    # Split card images into static/ once (cached across reruns)
    prepare_card_images()

    cards = discover_cards()
    if not cards:
        has_config = bool(
            _read_secret("CARDS_GITHUB_TOKEN") and _read_secret("CARDS_REPO")
        )
        if has_config:
            st.error(
                "Card library could not be loaded from the private repository.  \n"
                "Check that **CARDS_GITHUB_TOKEN** has `repo` read scope and "
                "**CARDS_REPO** is set to `owner/repo-name`."
            )
        else:
            st.info(
                "**No card images found.** Provide them in one of three ways:\n\n"
                "1. **Private repo** – set `CARDS_GITHUB_TOKEN` and `CARDS_REPO` "
                "in `.streamlit/secrets.toml` (see `.streamlit/secrets.toml.example`).\n"
                "2. **Volume mount** – `docker run -v /path/to/cards:/app/output/cards …`\n"
                "3. **Local extraction** – run `python src/extract_cards.py` to extract "
                "cards from the source PDFs."
            )
        return

    themes = sorted({c["theme"] for c in cards})
    board_html = build_board_html(cards, themes)

    # Slightly shorter to leave room for the top bar
    components.html(board_html, height=910, scrolling=False)


if __name__ == "__main__":
    main()
