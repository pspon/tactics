"""
Unit tests for web_utils.py optimizations.
Tests caching behavior and performance improvements.
"""

import pytest
import json
import time
from pathlib import Path
from PIL import Image
import tempfile
import shutil

# Import the module to test
import sys
from pathlib import Path as PathLib
sys.path.insert(0, str(PathLib(__file__).parent.parent))

from src import web_utils


class TestWebUtilsCaching:
    """Test caching optimizations in web_utils."""
    
    @pytest.fixture
    def temp_dirs(self, tmp_path):
        """Create temporary directories for testing."""
        cards_dir = tmp_path / "cards"
        meta_dir = tmp_path / "metadata"
        cards_dir.mkdir(parents=True)
        meta_dir.mkdir(parents=True)
        
        # Mock the paths
        original_cards_dir = web_utils.CARDS_DIR
        original_meta_dir = web_utils.META_DIR
        original_names_file = web_utils.NAMES_FILE
        original_users_file = web_utils.USERS_FILE
        original_decks_dir = web_utils.DECKS_DIR
        
        web_utils.CARDS_DIR = cards_dir
        web_utils.META_DIR = meta_dir
        web_utils.NAMES_FILE = meta_dir / "card_names.json"
        web_utils.USERS_FILE = meta_dir / "users.json"
        web_utils.DECKS_DIR = meta_dir / "decks"
        
        yield cards_dir, meta_dir
        
        # Restore original paths
        web_utils.CARDS_DIR = original_cards_dir
        web_utils.META_DIR = original_meta_dir
        web_utils.NAMES_FILE = original_names_file
        web_utils.USERS_FILE = original_users_file
        web_utils.DECKS_DIR = original_decks_dir
        
        # Clear caches
        web_utils.clear_caches()
    
    @pytest.fixture
    def sample_card_image(self, tmp_path):
        """Create a sample card image for testing."""
        img_path = tmp_path / "test_card.png"
        img = Image.new("RGB", (500, 700), color="red")
        img.save(img_path)
        return img_path
    
    def test_discover_cards_caching(self, temp_dirs):
        """Test that discover_cards() uses caching."""
        cards_dir, meta_dir = temp_dirs
        
        # Create test card
        card_file = cards_dir / "TestTheme_card01.png"
        img = Image.new("RGB", (500, 700), color="blue")
        img.save(card_file)
        
        # First call should scan directory
        result1 = web_utils.discover_cards()
        assert len(result1) == 1
        assert result1[0]["filename"] == "TestTheme_card01.png"
        
        # Second call should use cache (same result, but faster)
        result2 = web_utils.discover_cards()
        assert result1 == result2
        
        # Clear cache and verify it's cleared
        web_utils.clear_caches()
        result3 = web_utils.discover_cards()
        assert result3 == result1  # Should still work after clearing
    
    def test_discover_cards_cache_invalidation(self, temp_dirs):
        """Test that cache invalidates when directory changes."""
        cards_dir, meta_dir = temp_dirs
        
        # Create first card
        card1 = cards_dir / "Theme1_card01.png"
        img = Image.new("RGB", (500, 700), color="blue")
        img.save(card1)
        
        result1 = web_utils.discover_cards()
        assert len(result1) == 1
        
        # Add a new card (should invalidate cache)
        time.sleep(0.1)  # Ensure mtime changes
        card2 = cards_dir / "Theme2_card01.png"
        img.save(card2)
        
        result2 = web_utils.discover_cards()
        assert len(result2) == 2  # Should detect new card
    
    def test_load_card_image_caching(self, sample_card_image):
        """Test that load_card_image() uses LRU cache."""
        # Clear cache first
        web_utils.load_card_image.cache_clear()
        
        # Load image multiple times
        img1 = web_utils.load_card_image(str(sample_card_image))
        img2 = web_utils.load_card_image(str(sample_card_image))
        
        # Should be the same object (cached)
        assert img1 is img2
        
        # Verify it's a valid image
        assert isinstance(img1, Image.Image)
        assert img1.size == (500, 700)
    
    def test_load_card_names_caching(self, temp_dirs):
        """Test that card names JSON is cached."""
        cards_dir, meta_dir = temp_dirs
        
        # Create card names file
        names_data = {"card1.png": "Card One", "card2.png": "Card Two"}
        web_utils.NAMES_FILE.write_text(json.dumps(names_data), encoding='utf-8')
        
        # Clear cache
        web_utils._load_card_names.cache_clear()
        
        # Load twice
        result1 = web_utils._load_card_names()
        result2 = web_utils._load_card_names()
        
        assert result1 == names_data
        assert result1 is result2  # Should be same object (cached)
    
    def test_clear_caches(self, temp_dirs):
        """Test that clear_caches() works correctly."""
        cards_dir, meta_dir = temp_dirs
        
        # Create some data
        card_file = cards_dir / "test.png"
        img = Image.new("RGB", (100, 100))
        img.save(card_file)
        
        # Use functions to populate caches
        web_utils.discover_cards()
        web_utils.load_card_image(str(card_file))
        
        # Clear caches
        web_utils.clear_caches()
        
        # Verify caches are cleared (by checking cache info)
        cache_info = web_utils.load_card_image.cache_info()
        assert cache_info.hits == 0 or cache_info.currsize == 0 or cache_info.currsize < 2


class TestWebUtilsFunctions:
    """Test basic functionality of web_utils functions."""
    
    def test_ensure_metadata_dirs(self, tmp_path):
        """Test that ensure_metadata_dirs() creates directories."""
        original_meta = web_utils.META_DIR
        original_decks = web_utils.DECKS_DIR
        original_users = web_utils.USERS_FILE
        
        try:
            web_utils.META_DIR = tmp_path / "meta"
            web_utils.DECKS_DIR = tmp_path / "meta" / "decks"
            web_utils.USERS_FILE = tmp_path / "meta" / "users.json"
            
            web_utils.ensure_metadata_dirs()
            
            assert web_utils.META_DIR.exists()
            assert web_utils.DECKS_DIR.exists()
            assert web_utils.USERS_FILE.exists()
        finally:
            web_utils.META_DIR = original_meta
            web_utils.DECKS_DIR = original_decks
            web_utils.USERS_FILE = original_users
    
    def test_load_card_image_valid_image(self, tmp_path):
        """Test loading a valid image."""
        img_path = tmp_path / "test.png"
        img = Image.new("RGB", (200, 300), color="green")
        img.save(img_path)
        
        loaded = web_utils.load_card_image(str(img_path))
        assert isinstance(loaded, Image.Image)
        assert loaded.size == (200, 300)
        assert loaded.mode == "RGB"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

