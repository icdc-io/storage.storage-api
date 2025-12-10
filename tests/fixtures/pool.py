from typing import Dict

import pytest
from sqlalchemy import select

from app.database import db
from app.models.pool import Pools


def get_s3_pools() -> Dict[str, Pools]:
    """Return all S3 pools as {klass: pool}."""
    stmt = select(Pools).where(Pools.type == "s3")
    result = db.session.scalars(stmt)
    return {pool.klass: pool for pool in result}


def get_iscsi_pools() -> Dict[str, Pools]:
    """Return all iSCSI pools as {klass: pool}."""
    stmt = select(Pools).where(Pools.type == "iscsi")
    result = db.session.scalars(stmt)
    return {pool.klass: pool for pool in result}


@pytest.fixture(scope="package")
def s3_pool(s3_pools):
    """Return single S3 pool 'nvme'. 'nvme' takes as default"""
    yield s3_pools["nvme"]


@pytest.fixture(scope="package")
def iscsi_pool(iscsi_pools):
    """Return single iSCSI pool 'nvme'. 'nvme' takes as default"""
    yield iscsi_pools["nvme"]


@pytest.fixture(scope="package")
def s3_pools():
    """Return all S3 pools as {klass: pool} dict."""
    yield get_s3_pools()


@pytest.fixture(scope="package")
def iscsi_pools():
    """Return all iSCSI pools as {klass: pool} dict."""
    yield get_iscsi_pools()
