try:
    from backend.app.main import app  # noqa: F401
except ImportError:
    from app.main import app  # noqa: F401

