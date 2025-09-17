import pytest
from sqlalchemy import select

from app.database import db
from app.models.account import Accounts
from tests.factory.account import AccountFactory


@pytest.fixture(scope="package")
def seed_account():
    AccountFactory.create(
        name="aqa",
        description="Automated testing account, don't remove this account in tests, it has testing data on ceph that must not deleted."
    )
    AccountFactory.create(
        name="devel",
        description="Account for test operator role."
    )
    yield


def get_accounts():
    stmt = select(Accounts)
    result = db.session.scalars(stmt)
    res = {acc.name: acc for acc in result}
    return res


@pytest.fixture(scope="package")
def accounts(seed_account):
    return get_accounts()


@pytest.fixture(scope="package")
def aqa_acc(accounts):
    return accounts["aqa"]
