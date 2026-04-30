"""Importing every model here ensures Alembic autogenerate and Base.metadata see them."""

from .meal import Meal
from .user import User
from .water import WaterLog

__all__ = ["Meal", "User", "WaterLog"]
