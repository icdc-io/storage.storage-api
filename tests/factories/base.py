from typing import Any, Dict

from factory import DictFactory
from factory.alchemy import SQLAlchemyModelFactory

from app.database import db


class BaseFactory(SQLAlchemyModelFactory):
    """Base factories for SQLAlchemy models."""
    class Meta:
        abstract = True
        sqlalchemy_session = db.session
        sqlalchemy_session_persistence = "flush"


class BasePayloadFactory(DictFactory):
    """Base factories for JSON/dict payloads (filters out None)."""

    @classmethod
    def _build(cls, model_class: Any, *args, **kwargs) -> Dict[str, Any]:
        data = super()._build(model_class, *args, **kwargs)
        # Remove keys with None values
        return {k: v for k, v in data.items() if v is not None}
