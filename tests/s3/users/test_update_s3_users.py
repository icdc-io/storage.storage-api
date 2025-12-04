import pytest
from marshmallow import ValidationError

from tests.factories.headers import HeadersPayload
from tests.factories.s3_user import S3UserUpdatePayloadFactory
from tests.schemes.s3_user import S3UserTestResponseSchema


def test_permission_member_cannot_change_own_s3user_owner(api, s3_user):
    header = HeadersPayload.build(aqa_member=True, user=s3_user["owner"])
    new_owner = "member_own@example.com"
    payload = S3UserUpdatePayloadFactory.build(owner=new_owner)
    code, data = api.s3.users.update(s3_user["id"], payload, header)

    assert code == 200, f"Update failed: {code} {data}"
    assert data["owner"] != new_owner, "Permission failed: owner can not change the owner of s3 user."


def test_permission_member_cannot_change_s3user_with_different_owner(api, s3_user):
    header = HeadersPayload.build(aqa_member=True)
    payload = S3UserUpdatePayloadFactory.build(use_default=True)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 404, f"Update failed: {code} {data}"
    assert data["message"] == "S3 User not found or you haven't access for it.", \
           "Permission failed: owner can not change the owner of s3 user."


@pytest.mark.parametrize(
    "case",
    [
        {"role": "admin",    "user": "admin_user@example.com",    "account": "aqa"},
        {"role": "owner",    "user": "owner_user@example.com",    "account": "aqa"},
        {"role": "operator", "user": "operator_user@example.com", "account": "devel"},
    ],
    ids=lambda c: f"test_permission_privileged_role_can_change_different_s3users_in_one_account[{c['role']}]"
)
def test_permission_privileged_role_can_change_different_s3users_in_one_account(api, s3_user, case):
    role = case["role"]
    user = case["user"]
    account = case["account"]
    new_owner = "new_owner@example.com"

    header = HeadersPayload.build(account=account, role=role, user=user)
    payload = S3UserUpdatePayloadFactory.build(owner=new_owner)
    code, data = api.s3.users.update(s3_user["id"], payload, header)

    assert code == 200, f"Update failed: {code} {data}"
    assert data["owner"] == new_owner, f"Role {role} can't change owner."


@pytest.mark.parametrize(
    "role",
    ["admin", "owner"],
    ids=lambda r: f"test_admin_and_owner_cannot_change_another_account_s3user[{r}]"
)
def test_admin_and_owner_cannot_change_another_account_s3user(api, s3_user, role):
    header = HeadersPayload.build(account="devel", role=role)
    payload = S3UserUpdatePayloadFactory.build(use_default=True)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 404, f"Update success: {code} {data}"


def test_operator_can_change_another_account_s3user(api, s3_user):
    header = HeadersPayload.build(operator=True)
    payload = S3UserUpdatePayloadFactory.build(use_default=True)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 200, f"Update failed: {code} {data}"


@pytest.mark.parametrize(
    "quota, expected_message",
    [
        ({"buckets": 1000},     "S3User quota 'buckets' must not exceed account quota."),
        ({"data_size_mb": 1000},"S3User quota 'data_size_mb' must not exceed account quota."),
        ({"objects": 1000},     "S3User quota 'objects' must not exceed account quota."),
    ],
    ids=["buckets-overflow", "data_size_mb-overflow", "objects-overflow"],
)
def test_update_quota_overflow(api, s3_user, quota, expected_message):
    header = HeadersPayload.build(aqa_owner=True)
    payload = S3UserUpdatePayloadFactory.build(good=True, quota=quota)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 400, f"Expected 400, got {code}: {data}"
    # assert data["message"] == expected_message


@pytest.mark.parametrize(
    "role",
    ["member", "admin", "owner"],
    ids=lambda r: f"test_update_quota_success_for_role[{r}]"
)
def test_update_quota_success_for_roles(api, aqa, s3_user, role):
    header = HeadersPayload.build(account=aqa.name, role=role, user=s3_user["owner"])
    payload = S3UserUpdatePayloadFactory.build(good=True)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 200, f"Update failed: {code} {data}"


def test_update_quota_success_for_operator(api, s3_user):
    header = HeadersPayload.build(operator=True)
    payload = S3UserUpdatePayloadFactory.build(good=True)
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 200, f"Update failed: {code} {data}"


@pytest.mark.parametrize(
    "role",
    ["member", "admin", "owner"],
    ids=lambda r: f"test_update_quota_fail_for_role[{r}]"
)
def test_update_quota_fail_for_roles(api, aqa, s3_user, role):
    header = HeadersPayload.build(account=aqa.name, role=role, user=s3_user["owner"])
    payload = S3UserUpdatePayloadFactory.build(quota={"buckets": 10000, "objects": 10000, "data_size_mb": 10000})
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 400, f"Expected 400, got {code}: {data}"


def test_update_quota_fail_for_operator(api, s3_user):
    header = HeadersPayload.build(operator=True)
    payload = S3UserUpdatePayloadFactory.build(quota={"buckets": 10000, "objects": 10000, "data_size_mb": 10000})
    code, data = api.s3.users.update(s3_user["id"], payload, header)
    assert code == 400, f"Expected 400, got {code}: {data}"


def test_unlock_s3user(api, locked_s3_user):
    header = HeadersPayload.build(aqa_owner=True)
    payload = {"status": "active"}
    code, data = api.s3.users.update(locked_s3_user["id"], payload, header)
    assert code == 200, f"Unlock failed: {code} {data}"
    assert data["status"] == "active"


@pytest.mark.parametrize(
    "role",
    ["member", "admin", "owner"],
    ids=lambda r: f"test_update_quota_success_for_role[{r}]"
)
def test_update_quota_success_for_roles_in_locked_user(api, aqa, locked_s3_user, role):
    header = HeadersPayload.build(account=aqa.name, role=role, user=locked_s3_user["owner"])
    payload = S3UserUpdatePayloadFactory.build(good=True)
    code, data = api.s3.users.update(locked_s3_user["id"], payload, header)
    assert code == 200, f"Update failed: {code} {data}"


@pytest.mark.parametrize(
    "case",
    [
        {"id": "update-description",                 "description": "updated by pytest"},
        {"id": "update-owner+description",           "owner": "combo_owner@example.com",  "description": "combo description"},
        {"id": "update-owner+status",                "owner": "combo_owner2@example.com", "status": "locked"},
        {"id": "update-description+status",          "description": "combo case",         "status": "active"},
        {"id": "update-owner+description+status",    "owner": "complex_owner@example.com","description": "complex description","status": "active"},
    ],
    ids=lambda c: c["id"],
)
def test_update_combinations_success(case, api, aqa, s3_user):
    case.pop("id")
    headers = HeadersPayload.build(operator=True)
    code, data = api.s3.users.update(s3_user["id"], case, headers)
    assert code == 200, f"Update failed: {code} {data}"
    try:
        S3UserTestResponseSchema().load(data)
    except ValidationError as e:
        pytest.fail(f"S3 User validation failed: {e.messages}")


