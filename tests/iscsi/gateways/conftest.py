import pytest

from tests.fixtures.account import *
from tests.fixtures.iscsi_cluster import *
from tests.fixtures.iscsi_gateway import *
from tests.fixtures.iscsi_target import *
from tests.fixtures.pool import *


@pytest.fixture(scope="package")
def start_conn(make_connection):
    conn, cleanup = make_connection.start_connection()
    try:
        yield conn
    finally:
        cleanup()


@pytest.fixture(scope="package", autouse=True)
def seeding(start_conn, seed_operator):
    yield
