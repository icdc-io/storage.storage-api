import pytest
from marshmallow import ValidationError

from tests.schemes.iscsi_cluster import IscsiClusterResponseTestSchema
from tests.support.package_setup import setup_api_package


@pytest.fixture(scope="package", autouse=True)
def api_iscsi_clusters_package(make_connection):
    yield from setup_api_package(make_connection)


def validate_response(body, schema=IscsiClusterResponseTestSchema, many=True):
    """Validates response body against schema."""
    try:
        schema(many=many).load(body)
    except ValidationError as e:
        pytest.fail(f"Response schema validation failed: {e.messages}")
