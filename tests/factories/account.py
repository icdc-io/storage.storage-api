import factory

from app.models.account import Accounts
from tests.factories.base import BaseFactory


class AccountFactory(BaseFactory):
    """Factory for creating `Accounts` instances."""
    class Meta:
        model = Accounts

    # Auto-generated test data
    name = factory.Sequence(lambda n: f"account{n}")
    description = factory.Sequence(lambda n: f"acc{n} description.")
