import pytest

from tests.builders.s3_namespace import S3Env
from tests.support.s3_ceph import FakeS3Ceph


@pytest.fixture
def env(fake_s3_ceph) -> S3Env:
    built_env = S3Env(ceph=fake_s3_ceph)
    try:
        yield built_env
    finally:
        built_env.cleanup()


@pytest.fixture(autouse=True)
def fake_s3_ceph(monkeypatch):
    return FakeS3Ceph().install(monkeypatch)
