"""Importing every model here ensures Alembic autogenerate and Base.metadata see them."""

from .user import User

__all__ = ["User"]
