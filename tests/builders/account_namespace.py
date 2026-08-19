from dataclasses import dataclass
from types import SimpleNamespace

from sqlalchemy import select

from app.database import db
from app.models.pool import Pools
from tests.factories.account import AccountFactory


def load_pools(pool_type):
    stmt = select(Pools).where(Pools.type == pool_type)
    return {
        pool.klass: SimpleNamespace(
            id=pool.id,
            name=pool.name,
            klass=pool.klass,
            type=pool.type,
        )
        for pool in db.session.scalars(stmt)
    }


@dataclass
class AccountContext:
    account: object


class ScopeGuard:
    def _register_scope(
        self,
        *,
        kind: str,
        account,
        pool_name: str,
        pool,
        keys: set[tuple[int, int]],
    ):
        key = (account.id, pool.id)
        if key in keys:
            raise ValueError(
                f"Duplicate {kind} scope for account '{account.name}' "
                f"and pool '{pool_name}'. Reuse the existing scope context "
                "and create child objects from it instead of creating another "
                "scope for the same parent."
            )
        keys.add(key)


@dataclass
class AccountEnv:
    def cleanup(self):
        """DB-only env relies on test transaction rollback for cleanup."""
        return None

    def account(self, **kwargs):
        return AccountFactory.create(**kwargs)

    def accounts(self, *, count: int, **kwargs):
        return [self.account(**kwargs) for _ in range(count)]

    def account_scope(self, account=None, **account_kwargs):
        account = account or self.account(**account_kwargs)
        return AccountContext(account=account)
