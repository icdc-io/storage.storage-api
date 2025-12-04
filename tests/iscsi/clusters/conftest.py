import pytest
from marshmallow import ValidationError

from tests.fixtures.account import *
from tests.fixtures.iscsi_cluster import *
from tests.fixtures.iscsi_gateway import *
from tests.fixtures.iscsi_quota import *
from tests.fixtures.iscsi_target import *
from tests.fixtures.pool import *
from tests.schemes.iscsi_cluster import IscsiClusterResponseTestSchema


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


def validate_response(body, schema=IscsiClusterResponseTestSchema, many=True):
    """Validates response body against schema."""
    try:
        schema(many=many).load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")
