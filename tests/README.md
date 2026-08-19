# Tests Guide

This test suite is organized by how much of the system a test exercises.
Choose the smallest layer that proves the behavior:

```text
tests/unit/         schema and pure logic tests
tests/api/          Flask API tests with database state and fake Ceph
tests/integration/  Flask API tests with database state and real Ceph
```

The main idea is:

- Unit tests answer: "Does this validation or small rule work?"
- API tests answer: "Does the HTTP endpoint work with auth, DB state, and the
  expected service calls?"
- Integration tests answer: "Does this behavior really happen in Ceph?"

## Shared Architecture

Most test support code is shared across the three layers:

```text
tests/conftest.py        shared Flask app, API client, DB transaction, pool fixtures
tests/builders/          high-level test environments for valid object graphs
tests/factories/         DB model factories and API payload factories
tests/schemes/           response-shape assertions for API responses
tests/support/           fake Ceph, real Ceph helpers, API wrapper, package setup
```

### App And Database

The root `tests/conftest.py` creates the real Flask app once per test session.
It also seeds the database once.

API and integration tests use `make_connection` to create a package-scoped DB
transaction. Inside that transaction:

1. A DB connection is opened.
2. `db.session` is rebound to that connection.
3. all SQLAlchemy factories are rebound to the same session.
4. the package runs its tests.
5. the outer transaction is rolled back.

So API and integration tests can create real DB rows without permanently
changing the database.

### API Client

The `api` fixture wraps Flask's test client. Tests should use it instead of
calling `flask_client` directly.

Example:

```python
status, body = api.iscsi.disks.create(payload=payload, header=headers)
status, body = api.s3.users.list(query={"account": account.name}, header=headers)
```

The wrapper only hides HTTP mechanics: URL prefix, JSON payloads, CRUD method
names, and filter query formatting. It does not hide business behavior.

### Factories

Factories are low-level data builders.

There are two categories:

- Model factories create database rows.
- Payload factories create request bodies.

Architecturally, factories should be used for data shape, not for business
setup. If a test needs an account with quota, target, disk, user, or bucket,
prefer the `env` builders because they create related objects consistently.

### Builders

Builders are the preferred way to create business state.

For example, an iSCSI disk needs a valid chain:

```text
account -> cluster -> quota -> target -> disk
```

An S3 bucket needs a valid chain:

```text
account -> quota -> user -> bucket
```

The builder envs create those chains in a readable way:

```python
scope = env.scope(pool_name="nvme")
disk_ctx = env.disk_scope(pool_name="nvme")
bucket_ctx = env.bucket_scope(pool_name="nvme")
```

### ScopeGuard

`ScopeGuard` protects tests from accidentally creating duplicate quota scope
for the same account and pool inside one builder environment.

This matters because quota is usually one-per-account-per-pool. If a test calls
`env.scope(account=account, pool_name="nvme")` twice, the test probably meant
to reuse the first scope and create more child objects from it.

Use this pattern:

```python
scope = env.scope(account=account, pool_name="nvme")
disk1 = env.disk(target=scope.target)
disk2 = env.disk(target=scope.target)
```

Not this:

```python
scope1 = env.scope(account=account, pool_name="nvme")
scope2 = env.scope(account=account, pool_name="nvme")
```

### Response Schemas

Schemas under `tests/schemes/` are test-only response contracts. They are used
when a test needs to verify that an API response has the expected structure.

Use direct assertions for the behavior itself:

```python
assert body["name"] == payload["name"]
assert body["pool"]["id"] == scope.quota.pool_id
```

Use response schemas when the full response shape matters.

## Unit Tests

Unit tests live in `tests/unit/`.

They should be fast and isolated. They usually test:

- Marshmallow schema validation.
- quota calculations.
- small model or service rules that do not need HTTP.

### Unit Setup

`tests/unit/conftest.py` replaces the app fixture with a tiny Flask app. Unit
tests should not need the real app startup, real database setup, or Ceph.

Most unit tests create plain payload dictionaries or simple fake quota objects
inside the test file. That is intentional: unit tests should make the rule
under test obvious.

### Unit Pattern

```python
def test_schema_rejects_invalid_name():
    payload = make_payload(name="bad name")

    with pytest.raises(ValidationError):
        SomeSchema().load(payload)
```

Use unit tests when the behavior can be proven without making an HTTP request.

## API Tests

API tests live in `tests/api/`.

They exercise the real Flask route, request parsing, auth headers, database
queries, response formatting, and mocked/fake Ceph calls.

They do not talk to real Ceph.

### API Setup

Each API package has an autouse package fixture that calls
`setup_api_package(make_connection)`.

That setup:

1. starts a rollback-protected DB package transaction.
2. creates the `devel` account used by operator headers.
3. lets each test create its own account, quota, user, disk, etc.

API tests use domain-specific `env` fixtures:

- `tests/api/s3/conftest.py` provides `S3Env`.
- `tests/api/iscsi/conftest.py` provides `IscsiEnv`.

These envs create real database rows, but external storage behavior is fake.

### API S3 Fake

S3 API tests use `FakeS3Ceph`.

The fake stores enough Ceph-like state for API behavior:

- user status, quota, usage, and keys.
- bucket objects.
- injected S3 create errors for failure tests.

This lets S3 API tests verify enrichment, bucket listing, quota behavior, and
error handling without real Ceph.

### API iSCSI Mock

iSCSI API tests use a mocked `IscsiTargets.iscsi_service()`.

By default the mock returns successful Ceph-like responses. Tests can override
responses to check failure handling:

```python
mocked_iscsi_service.create_disk.return_value = {
    "code": 500,
    "data": "ceph failed",
}
```

API tests should assert both:

- what the HTTP endpoint returned.
- whether the fake/mocked service was called or not called.

### API Pattern

```python
def test_operator_can_create_disk(api, env, mocked_iscsi_service):
    scope = env.scope(pool_name="nvme")
    payload = IscsiDiskCreatePayload.build(
        account_name=scope.account.name,
        pool_id=scope.quota.pool_id,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201)
    assert body["target"]["id"] == scope.target.id
    mocked_iscsi_service.create_disk.assert_called_once()
```

Use API tests for:

- RBAC and account isolation.
- status codes and error messages.
- request payload handling.
- response structure.
- database side effects.
- fake Ceph or mocked iSCSI service calls.

## Integration Tests

Integration tests live in `tests/integration/`.

They exercise the real Flask API, real database state, and real external Ceph
behavior. They are slower and depend on environment configuration.

Use integration tests only when fake Ceph cannot prove the behavior.

### Integration Setup

Each integration package has an autouse package fixture that calls
`setup_integration_package(make_connection)`.

That setup:

1. starts a rollback-protected DB package transaction.
2. creates the `devel` operator account.
3. reads `FIXTURES_FILE`, or falls back to `config/fixtures_file.yaml`.
4. creates configured accounts, quotas, clusters, gateways, and targets.
5. returns an `IntegrationPackage`.

The default fixture file creates an `aqa` account with S3 and iSCSI quota state
for the configured pools.

### Integration Envs

Integration tests use Ceph-aware envs:

- `CephS3Env` for real S3 users and buckets.
- `CephIscsiEnv` for real iSCSI disks, clients, and assignments.
- `CephAccountEnv` when a test needs both S3 and iSCSI namespaces.

These envs differ from API envs in one important way: creating a resource may
also create it in real Ceph.

Example:

```python
scope = env.scope(pool_name="nvme")
disk = env.disk(target=scope.target)
```

In an iSCSI integration test, this creates a DB disk and a real Ceph disk.

### Cleanup

Database rows are rolled back by the package transaction, but real Ceph
resources must be explicitly tracked so the env can remove them.

When an integration env creates a resource directly, it tracks the resource.
When an API call creates a real Ceph resource, the test must track it manually:

```python
status, body = api.iscsi.disks.create(payload=payload, header=headers)

disk = IscsiDisks.query.filter_by(id=body["id"]).first()
env.track_disk(disk)
```

This is the most important integration-test rule: if the test creates a real
Ceph object through the API, track it.

### Integration Pattern

```python
def test_create_disk_in_real_ceph(api, env):
    scope = env.scope(pool_name="nvme")
    payload = IscsiDiskCreatePayload.build(
        account_name=env.account.name,
        pool_id=scope.quota.pool_id,
    )
    headers = HeadersPayload.build(operator=True)

    status, body = api.iscsi.disks.create(payload=payload, header=headers)

    assert status in (200, 201)

    disk = IscsiDisks.query.filter_by(id=body["id"]).first()
    env.track_disk(disk)
    assert verify_disk_exists(disk)
```

Use integration tests for:

- verifying real Ceph disk creation, update, delete.
- verifying real iSCSI client assignment and unassignment.
- verifying real S3 user and bucket state.
- checking behavior across real configured pools.

## How To Choose Helpers

Use `env` when the test needs valid business state.

Use factories when the test needs a payload or a single low-level DB row.

Use response schemas when response shape matters.

Avoid hidden setup. A new reader should be able to see the account, pool, quota,
target, user, disk, or bucket that matters for the test.

## Adding A New Test

1. Choose the layer: unit, API, or integration.
2. Create only the state needed for the behavior.
3. Prefer `env.scope()` or `env.*_scope()` for parent state.
4. Use payload factories for request bodies.
5. Use `HeadersPayload` for auth headers.
6. Assert the behavior, not only the status code.
7. In integration tests, track real Ceph resources created through API calls.

## Useful Commands

```bash
pytest tests/unit
pytest tests/api
pytest tests/integration
pytest -m "not integration"
pytest tests/api/iscsi/disks/test_create.py -k create
```
