import importlib

def check(name):
    try:
        m = importlib.import_module(name)
        print(f"{name} available: True")
        print(f"{name} version: {getattr(m, '__version__', 'unknown')}")
    except Exception as e:
        print(f"{name} available: False; error: {e}")


if __name__ == '__main__':
    check('PIL')
    check('streamlit')
