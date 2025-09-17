from app.models.account import Accounts
from tests.factory.base import BaseFactory


class AccountFactory(BaseFactory):
    class Meta:
        model = Accounts
