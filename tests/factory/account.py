from tests.factory.base import BaseFactory
from app.models.account import Accounts


class AccountFactory(BaseFactory):
    class Meta:
        model = Accounts
