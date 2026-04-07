"""
Performance tests for caching optimizations.
"""

import pytest
import time
from pathlib import Path
from PIL import Image
import tempfile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import web_utils


class TestCachingPerformance:
    """Test that caching actually improves performance."""
    
    @pytest.fixture
    def temp_cards_dir(self, tmp_path):
        """Create temporary cards directory with multiple images."""
        cards_dir = tmp_path / "cards"
        cards_dir.mkdir(parents=True)
        
        # Create 10 test card images
        for i in range(10):
            img_path = cards_dir / f"Theme_card{i:02d}.png"
            img = Image.new("RGB", (500, 700), color=(i*25, 100, 150))
            img.save(img_path)
        
        # Mock the CARDS_DIR
        original = web_utils.CARDS_DIR
        web_utils.CARDS_DIR = cards_dir
        yield cards_dir
        web_utils.CARDS_DIR = original
        web_utils.clear_caches()
    
    def test_discover_cards_performance(self, temp_cards_dir):
        """Test that cached discover_cards() is faster."""
        # Clear cache
        web_utils.clear_caches()
        
        # First call (uncached)
        start = time.time()
        result1 = web_utils.discover_cards()
        time1 = time.time() - start
        
        # Second call (cached)
        start = time.time()
        result2 = web_utils.discover_cards()
        time2 = time.time() - start
        
        # Cached call should be significantly faster
        # (at least 2x faster, but often much more)
        assert time2 < time1, f"Cached call ({time2:.4f}s) should be faster than uncached ({time1:.4f}s)"
        assert result1 == result2
        
        # Verify we got all cards
        assert len(result1) == 10
    
    def test_load_image_performance(self, temp_cards_dir):
        """Test that cached load_card_image() is faster."""
        cards_dir = temp_cards_dir
        card_path = cards_dir / "Theme_card00.png"
        
        # Clear cache
        web_utils.load_card_image.cache_clear()
        
        # First call (uncached - loads from disk)
        start = time.time()
        img1 = web_utils.load_card_image(str(card_path))
        time1 = time.time() - start
        
        # Second call (cached - from memory)
        start = time.time()
        img2 = web_utils.load_card_image(str(card_path))
        time2 = time.time() - start
        
        # Cached call should be much faster
        assert time2 < time1, f"Cached call ({time2:.6f}s) should be faster than uncached ({time1:.6f}s)"
        assert img1 is img2  # Should be same object
    
    def test_cache_hit_rate(self, temp_cards_dir):
        """Test that cache hit rate improves with repeated access."""
        cards_dir = temp_cards_dir
        
        # Clear cache
        web_utils.load_card_image.cache_clear()
        
        # Load same image multiple times
        card_path = str(cards_dir / "Theme_card00.png")
        
        for _ in range(5):
            web_utils.load_card_image(card_path)
        
        cache_info = web_utils.load_card_image.cache_info()
        
        # Should have hits (at least 4 hits from 5 calls)
        assert cache_info.hits >= 4
        assert cache_info.currsize >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

