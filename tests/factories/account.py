from typing import List

import factory
from sqlalchemy import select

from app.database import db
from app.models.account import Accounts
from tests.factories.base import BaseFactory


class AccountFactory(BaseFactory):
    """Factory for creating `Accounts` instances."""
    class Meta:
        model = Accounts

    # Auto-generated test data
    name = factory.Sequence(lambda n: f"account{n}")
    description = factory.Sequence(lambda n: f"acc{n} description.")


def get_all_accounts() -> List[Accounts]:
    """Return all accounts from DB."""
    stmt = select(Accounts)
    return db.session.scalars(stmt).all()
