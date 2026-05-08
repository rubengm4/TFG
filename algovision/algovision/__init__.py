try:
    from .celery import app as celery_app  # type: ignore
except Exception:  # pragma: no cover
    celery_app = None  # type: ignore

__all__ = ("celery_app",)
