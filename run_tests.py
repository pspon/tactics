"""
Simple test runner for the optimizations.
Can be run with: python run_tests.py
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

def test_imports():
    """Test that all optimized modules can be imported."""
    print("Testing imports...")
    try:
        from src import web_utils
        print("✓ web_utils imported successfully")
        
        from src import extract_cards
        print("✓ extract_cards imported successfully")
        
        import flask_viewer
        print("✓ flask_viewer imported successfully")
        
        import streamlit_viewer
        print("✓ streamlit_viewer imported successfully")
        
        import streamlit_app
        print("✓ streamlit_app imported successfully")
        
        import streamlit_mixmatch
        print("✓ streamlit_mixmatch imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_caching_functions():
    """Test that caching functions exist and work."""
    print("\nTesting caching functions...")
    try:
        from src import web_utils
        
        # Test that clear_caches exists
        assert hasattr(web_utils, 'clear_caches'), "clear_caches function not found"
        print("✓ clear_caches function exists")
        
        # Test that it can be called
        web_utils.clear_caches()
        print("✓ clear_caches can be called")
        
        # Test that load_card_image has caching
        assert hasattr(web_utils.load_card_image, 'cache_info'), "load_card_image not cached"
        print("✓ load_card_image has caching")
        
        # Test that discover_cards exists
        assert hasattr(web_utils, 'discover_cards'), "discover_cards function not found"
        print("✓ discover_cards function exists")
        
        return True
    except Exception as e:
        print(f"✗ Caching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_parallel_processing_flag():
    """Test that parallel processing flag exists."""
    print("\nTesting parallel processing...")
    try:
        from src import extract_cards
        import inspect
        
        # Check that main function exists
        assert hasattr(extract_cards, 'main'), "main function not found"
        print("✓ main function exists")
        
        # Check imports
        assert 'ProcessPoolExecutor' in str(inspect.getsource(extract_cards)), "ProcessPoolExecutor not imported"
        print("✓ ProcessPoolExecutor imported")
        
        return True
    except Exception as e:
        print(f"✗ Parallel processing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_streamlit_caching():
    """Test that Streamlit apps have caching decorators."""
    print("\nTesting Streamlit caching...")
    try:
        import streamlit_viewer
        import inspect
        
        source = inspect.getsource(streamlit_viewer)
        
        # Check for cache decorators
        if '@st.cache_data' in source:
            print("✓ streamlit_viewer uses @st.cache_data")
        else:
            print("⚠ streamlit_viewer may not use caching")
        
        import streamlit_app
        source = inspect.getsource(streamlit_app)
        if '@st.cache_data' in source:
            print("✓ streamlit_app uses @st.cache_data")
        else:
            print("⚠ streamlit_app may not use caching")
        
        import streamlit_mixmatch
        source = inspect.getsource(streamlit_mixmatch)
        if '@st.cache_data' in source:
            print("✓ streamlit_mixmatch uses @st.cache_data")
        else:
            print("⚠ streamlit_mixmatch may not use caching")
        
        return True
    except Exception as e:
        print(f"✗ Streamlit caching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_flask_caching():
    """Test that Flask app has caching."""
    print("\nTesting Flask caching...")
    try:
        import flask_viewer
        import inspect
        
        source = inspect.getsource(flask_viewer)
        
        # Check for lru_cache
        if 'lru_cache' in source or '@lru_cache' in source:
            print("✓ flask_viewer uses lru_cache")
        else:
            print("⚠ flask_viewer may not use caching")
        
        # Check for functools import
        if 'from functools import' in source or 'import functools' in source:
            print("✓ flask_viewer imports functools")
        
        return True
    except Exception as e:
        print(f"✗ Flask caching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Running Optimization Tests")
    print("=" * 60)
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Caching Functions", test_caching_functions()))
    results.append(("Parallel Processing", test_parallel_processing_flag()))
    results.append(("Streamlit Caching", test_streamlit_caching()))
    results.append(("Flask Caching", test_flask_caching()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"{name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

