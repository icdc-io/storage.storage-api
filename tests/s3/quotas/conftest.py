import pytest

from tests.fixtures.account import *
from tests.fixtures.bucket import *
from tests.fixtures.pool import *
from tests.fixtures.s3_quota import *
from tests.fixtures.s3_user import *


@pytest.fixture(scope="package")
def start_conn(make_connection):
    conn, cleanup = make_connection.start_connection()
    try:
        yield conn
    finally:
        cleanup()


@pytest.fixture(scope="package", autouse=True)
def seeding(start_conn, seed_full_environment):
    yield
