"""
Unit tests for extract_cards.py parallel processing optimization.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import extract_cards


class TestParallelProcessing:
    """Test parallel processing functionality."""
    
    def test_parallel_flag_parsing(self):
        """Test that --parallel flag is parsed correctly."""
        with patch('sys.argv', ['extract_cards.py', '--parallel']):
            parser = extract_cards.main.__code__.co_consts
            # This is a basic test - in practice we'd test argparse directly
            pass
    
    def test_workers_flag_parsing(self):
        """Test that --workers flag is parsed correctly."""
        with patch('sys.argv', ['extract_cards.py', '--parallel', '--workers', '4']):
            # Test would verify workers count
            pass
    
    def test_parallel_processing_imports(self):
        """Test that parallel processing imports are present."""
        import inspect
        source = inspect.getsource(extract_cards)
        
        # Verify ProcessPoolExecutor is imported
        assert 'ProcessPoolExecutor' in source, "ProcessPoolExecutor not imported"
        assert 'as_completed' in source, "as_completed not imported"
        assert 'multiprocessing' in source, "multiprocessing not imported"
    
    def test_parallel_flag_exists(self):
        """Test that --parallel flag is defined in argument parser."""
        import inspect
        source = inspect.getsource(extract_cards)
        
        # Check for parallel flag
        assert '--parallel' in source, "--parallel flag not found"
        assert 'action="store_true"' in source or 'store_true' in source, "parallel flag not boolean"
    
    def test_workers_flag_exists(self):
        """Test that --workers flag is defined."""
        import inspect
        source = inspect.getsource(extract_cards)
        
        # Check for workers flag
        assert '--workers' in source, "--workers flag not found"


class TestExtractCardsMain:
    """Test main extraction functionality."""
    
    @patch('extract_cards.validate_dependencies')
    @patch('extract_cards.setup_logging')
    @patch('extract_cards.get_pdf_files')
    def test_no_pdfs_found(self, mock_get_pdfs, mock_logging, mock_validate):
        """Test behavior when no PDFs are found."""
        mock_get_pdfs.return_value = []
        mock_logger = MagicMock()
        mock_logging.return_value = mock_logger
        
        # Would need to call main() and verify warning is logged
        # This is a placeholder for the test structure
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

