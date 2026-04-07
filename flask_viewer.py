from flask import Flask, render_template, send_file, request
from pathlib import Path
import io
from PIL import Image
from functools import lru_cache
import json

from src.web_utils import discover_cards, load_card_image

app = Flask(__name__)

CARDS_DIR = Path("output/cards")
LAYOUTS_DIR = Path("layouts")

# Cache for card discovery (invalidated manually or on restart)
_cards_cache = None

def _split_card_image(img: Image.Image):
    """Split an image into front and back. Front on left, back on right."""
    w, h = img.size
    mid = w // 2
    front = img.crop((0, 0, mid, h))
    back = img.crop((mid, 0, w, h))
    return front, back

@lru_cache(maxsize=256)
def _get_card_side_cached(card_path: str, side: str) -> bytes:
    """Cache split card images as bytes."""
    img = load_card_image(card_path)
    front, back = _split_card_image(img)
    side_img = front if side == 'front' else back
    buf = io.BytesIO()
    side_img.save(buf, format='PNG')
    return buf.getvalue()

@app.route('/')
def index():
    global _cards_cache
    if _cards_cache is None:
        _cards_cache = discover_cards()
    cards = _cards_cache
    themes = sorted(set(c["theme"] for c in cards))
    return render_template('index.html', cards=cards, themes=themes)

@app.route('/card/<side>/<filename>')
def get_card_side(side, filename):
    if side not in ['front', 'back']:
        return "Invalid side", 400
    card_path = CARDS_DIR / filename
    if not card_path.exists():
        return "Card not found", 404
    try:
        # Use cached version
        img_bytes = _get_card_side_cached(str(card_path), side)
        buf = io.BytesIO(img_bytes)
        buf.seek(0)
        return send_file(buf, mimetype='image/png')
    except Exception as e:
        return str(e), 500

@app.route('/save_layout', methods=['POST'])
def save_layout():
    data = request.get_json()
    name = data['name']
    layout = data['layout']
    with open(LAYOUTS_DIR / f"{name}.json", 'w') as f:
        json.dump(layout, f)
    return {'status': 'saved'}

@app.route('/load_layout/<name>')
def load_layout(name):
    path = LAYOUTS_DIR / f"{name}.json"
    if not path.exists():
        return {'error': 'not found'}, 404
    with open(path) as f:
        layout = json.load(f)
    return layout

@app.route('/list_layouts')
def list_layouts():
    files = list(LAYOUTS_DIR.glob('*.json'))
    names = [f.stem for f in files]
    return {'layouts': names}

@app.route('/delete_layout/<name>', methods=['DELETE'])
def delete_layout(name):
    path = LAYOUTS_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return {'status': 'deleted'}
    return {'error': 'not found'}, 404

if __name__ == '__main__':
    # Run Flask app
    # Default: http://localhost:5000
    # To change host/port, modify below or use: flask run --host=0.0.0.0 --port=5000
    app.run(debug=True, host='0.0.0.0', port=5000)
