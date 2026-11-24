"""Modular FastAPI APIRouter package for DataX-Ray Enterprise Server."""
from .predict_router import build_predict_router
from .i18n_router import build_i18n_router
from .boardroom_router import build_boardroom_router
from .system_router import build_system_router

__all__ = [
    "build_predict_router",
    "build_i18n_router",
    "build_boardroom_router",
    "build_system_router",
]
