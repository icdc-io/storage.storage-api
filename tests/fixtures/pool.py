import pytest
from sqlalchemy import select

from app.database import db
from app.models.pool import Pools


def get_s3_pools():
    stmt = select(Pools).where(Pools.type == "s3")
    result = db.session.scalars(stmt)
    res = {pool.klass: pool for pool in result}
    return res


@pytest.fixture(scope="package")
def s3_pools():
    return get_s3_pools()


@pytest.fixture(scope="package")
def s3_ssd(s3_pools):
    return s3_pools["ssd"]
