"""RigBridge Backend - API Modul."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI


def create_app(*args, **kwargs) -> 'FastAPI':
    """Lazy-Proxy für create_app, um runpy-Warnungen zu vermeiden."""
    from .main import create_app as _create_app
    return _create_app(*args, **kwargs)


def create_router():
    """Lazy-Proxy für create_router."""
    from .routes import create_router as _create_router

    return _create_router()


__all__ = ['create_app', 'create_router']
