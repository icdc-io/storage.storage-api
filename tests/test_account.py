# import pytest
# from flask.testing import FlaskClient
# from marshmallow import ValidationError
#
# from tests.schemes.account import AccountResponseSchema
#
#
# @pytest.mark.parametrize(
#     "headers, expected_status, expected_message",
#     [
#         (
#             {
#                 "x-auth-account": "devel",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Role name is required in x-auth-role header.",
#         ),
#         (
#             {
#                 "x-auth-role": "admin",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Account name is required in x-auth-account header.",
#         ),
#         (
#             {
#                 "x-auth-account": "devel",
#                 "x-auth-role": "wrong_role",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Invalid auth parameters. Role name is not found.",
#         ),
#         (
#             {
#                 "x-auth-account": "wrong_account",
#                 "x-auth-role": "admin",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Invalid auth parameters. Account name is not found.",
#         ),
#     ],
#     ids=[
#         "missing x-auth-role",
#         "missing x-auth-account",
#         "wrong x-auth-role",
#         "wrong x-auth-account",
#     ],
# )
# def test_get_accounts_bad_cases(
#     client: FlaskClient,
#     headers,
#     expected_status,
#     expected_message,
# ):
#     response = client.get("/api/v2/accounts", headers=headers)
#     assert response.status_code == expected_status
#     assert response.get_json()["message"] == expected_message
#
#
# def test_get_accounts_success(client: FlaskClient, headers_factory):
#     response = client.get("/api/v2/accounts", headers=headers_factory.build(operator=True))
#     assert response.status_code == 200
#     accounts_info = response.get_json()
#     try:
#         AccountResponseSchema(many=True).load(accounts_info)
#     except ValidationError as e:
#         pytest.fail(f"Accounts validation failed: {e.messages}")
#
#
# @pytest.mark.parametrize(
#     "headers, expected_status, expected_message",
#     [
#         (
#             {
#                 "x-auth-account": "devel",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Role name is required in x-auth-role header.",
#         ),
#         (
#             {
#                 "x-auth-role": "admin",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Account name is required in x-auth-account header.",
#         ),
#         (
#             {
#                 "x-auth-account": "devel",
#                 "x-auth-role": "wrong_role",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Invalid auth parameters. Role name is not found.",
#         ),
#         (
#             {
#                 "x-auth-account": "wrong_account",
#                 "x-auth-role": "admin",
#                 "Content-Type": "application/json",
#             },
#             401,
#             "Invalid auth parameters. Account name is not found.",
#         ),
#     ],
#     ids=[
#         "missing x-auth-role",
#         "missing x-auth-account",
#         "wrong x-auth-role",
#         "wrong x-auth-account",
#     ],
# )
# def test_get_account_bad_cases(
#     client: FlaskClient,
#     headers,
#     expected_status,
#     expected_message,
# ):
#     response = client.get("/api/v2/accounts/devel", headers=headers)
#     assert response.status_code == expected_status
#     assert response.get_json()["message"] == expected_message
#
#
# def test_get_account_success(client: FlaskClient, headers_factory):
#     response = client.get("/api/v2/accounts/devel", headers=headers_factory.build(operator=True))
#     assert response.status_code == 200
#     account_info = response.get_json()
#     print(account_info)
#     try:
#         AccountResponseSchema().load(account_info)
#     except ValidationError as e:
#         pytest.fail(f"Account validation failed: {e.messages}")
