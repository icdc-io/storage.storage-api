"""
This module is used for authorization actions in Flask application
"""

import base64
import functools
import json
import time
from datetime import datetime

import jwt
import requests
from flask import Request, abort, request
from jwt.algorithms import RSAAlgorithm as rsa

from app import consts
from app.lib.gateway import concat_url, gateway
from app.lib.request_utils import bad_gateway, dig, is_failed, log, unauthorized

SSO_TOKEN = ""
PUBLIC_KEY = ""
role = ""
account = ""
auth_group_header = None


methods = {
    "GET": requests.get,
    "POST": requests.post,
    "PUT": requests.put,
    "PATCH": requests.patch,
    "DELETE": requests.delete,
}

SSO_TOKEN_ENDPOINT = f"realms/{consts.SSO_REALM}/protocol/openid-connect/token"
SSO_CERTS_ENDPOINT = f"realms/{consts.SSO_REALM}/protocol/openid-connect/certs"
LOCATION_ADMIN_GROUP = consts.LOCATION_ADMIN_GROUP
JWT_ALGORITHM = "RS256"

MEMBER_ROLE = "member"
ADMIN_ROLE = "admin"
OPERATOR_ROLE = "operator"
PRIVELEGED_ROLES = [ADMIN_ROLE, OPERATOR_ROLE]

AUTHORIZATION_HEADER = "Authorization"
X_AUTH_ROLE_HEADER = "x-auth-role"
X_AUTH_ACCOUNT_HEADER = "x-auth-account"
X_AUTH_GROUP_HEADER = "x-auth-group"


valid_roles: set[str] = {"member", "admin", "operator", "owner", "billing"}


def check_token_exp(token: str) -> bool:
    """
    Check if the token is expired based on the 'exp' field in the payload.

    Args:
        token (str): The token to be checked.

    Returns:
        bool: True if the token is valid, False otherwise.
    """
    # Extract the payload from the token
    data = token.split(".")[1]
    # Fixing base64 string, because python base64 lib
    # can throw in some cases "binascii.Error: Incorrect padding"

    # Fix base64 padding issue
    data += "=" * ((4 - len(data) % 4) % 4)

    # Decode the payload and load it as a JSON object
    payload = json.loads(base64.b64decode(data).decode())

    # Check if the token expiration time is greater than the current time
    if payload["exp"] > time.time():
        log.info(f"Current token valid until: {datetime.fromtimestamp(payload['exp'])}")
        log.info(f"Current token valid until: {datetime.fromtimestamp(payload['exp'])}")
        return True
    return False


def get_jwt_token(username, password):
    """
    Function to get a JWT token using the provided username and password.

    Args:
        username (str): The username for authentication.
        password (str): The password for authentication.

    Returns:
        str: The JWT token if successful, or an error response if authentication failed.
    """

    url = concat_url(consts.SSO_URL, SSO_TOKEN_ENDPOINT)
    data = {
        "client_id": consts.SSO_CLIENT_ID,
        "grant_type": "password",
        "username": username,
        "password": password,
    }
    resp = gateway(url, "POST", data=data)
    if is_failed(resp):
        return resp
    try:
        data = resp.json()
        return data["access_token"]
    except KeyError as k_e:
        log.error(k_e, exc_info=True)
        return bad_gateway({"error": "Authentication failed in the upstream system"})
    except json.decoder.JSONDecodeError as j_e:
        log.error(j_e, exc_info=True)
        return bad_gateway({"error": "Authentication failed in the upstream system"})


def roles(auth_info, account):
    """
    Retrieve the roles associated with the specified account from the provided auth_info.

    :param auth_info: The authentication information dictionary.
    :param account: The account for which to retrieve the roles.
    :return: A list of roles associated with the specified account, or an empty list if no roles are found.
    """

    roles_set = dig(auth_info, "external", "accounts", account, "roles")
    if isinstance(roles_set, dict):
        return roles_set
    return []


def all_roles(auth_info):
    """
    Retrieve all roles from the provided authentication information.

    :param auth_info: The authentication information containing external accounts.
    :type auth_info: dict
    :return: A set of all roles from the external accounts.
    :rtype: set
    """

    accounts_map = dig(auth_info, "external", "accounts")
    role_set = set()
    for account in accounts_map:
        role_set.update(accounts_map[account].get("roles"))
    return role_set


def get_auth_info():
    """
    This function retrieves the authorization information from the request headers.
    If no authorization header is present or it's empty, it returns an unauthorized
    response with status code 401. Otherwise, it attempts to authenticate using the
    provided authorization header and returns the result.
    """

    # Retrieve the Authorization header from the request
    auth_header = request.headers.get(AUTHORIZATION_HEADER)

    # Log the Authorization header for debugging purposes
    log.debug(f"Auth Header {auth_header}")

    # If no Authorization header is present or it's empty, return an unauthorized response
    if not auth_header:
        return unauthorized(401)

    # If an Authorization header is present, attempt to authenticate and return the result
    return authenticate(auth_header)


def authenticate(auth_header):
    """
    Authenticate the user based on the provided authentication header.

    Args:
        auth_header (str): The authentication header containing the authentication method and payload.

    Returns:
        dict: The authentication information for the user.
    """
    auth_method = {"Bearer": validate_bearer, "Basic": validate_basic}
    try:
        auth_alg, auth_payload = auth_header.split(" ", 1)
    except ValueError:
        # Return unauthorized status if unable to split the header
        return unauthorized(401)
    method = auth_method.get(auth_alg)
    if method is None:
        # Return unauthorized status if method is not found
        return unauthorized(401)

    # Authenticate the user using the selected method and payload
    auth_info = method(auth_payload)
    return auth_info


def validate_bearer(token):
    """
    Validates the bearer token and returns the decoded authentication information if
    successful. Otherwise, it returns the appropriate error response.
    """

    # If the token is empty or None, return unauthorized
    if token is None or len(token) == 0:
        return unauthorized()

    try:
        # Decode the token using the public key and set the required algorithm and audience
        auth_info = jwt.decode(
            token,
            get_public_key(),
            algorithms=[JWT_ALGORITHM],
            audience=consts.SSO_CLIENT_ID,
        )
        return auth_info
    # If the token is invalid, log the error and return HTTP 401
    except jwt.InvalidTokenError as i_e:
        log.error(i_e, exc_info=True)
        abort(401)
    # If a required key is missing, log the error and return HTTP 502
    except KeyError as k_e:
        log.error(k_e, exc_info=True)
        abort(502)
    # If the token can't be decoded as JSON, log the error and return HTTP 502
    except json.decoder.JSONDecodeError as j_e:
        log.error(j_e, exc_info=True)
        abort(502)


def validate_basic(token):
    """
    Validate the provided token by decoding it and extracting the username and password.
    If an error occurs during decoding, log the error and abort with status code 401.
    After decoding the token, retrieve the JWT token using the extracted username and password.
    Finally, validate the retrieved JWT token and return the result.
    """

    # Decode the token and extract the username and password
    try:
        username, passwd = base64.b64decode(token).decode().split(":")
    except ValueError as v_e:
        # Log the error and abort with status code 401 if decoding fails
        log.error(v_e, exc_info=True)
        abort(401)

    # Retrieve the JWT token using the extracted username and password
    jwt_token = get_jwt_token(username, passwd)

    # Validate the retrieved JWT token and return the result
    return validate_bearer(jwt_token)


def get_public_key():
    """
    Get the public key from the SSO service. If the PUBLIC_KEY global variable is not None
    or empty, return it. Otherwise, retrieve the public key from the SSO service by
    making a GET request to the appropriate URL and parsing the response to find the
    key with algorithm "RS256". If successful, convert the selected key to RSA format
    and assign it to PUBLIC_KEY before returning it. If any exceptions occur during the
    process, log the error and abort with the appropriate status code.
    """
    global PUBLIC_KEY  # pylint:disable=global-statement
    if PUBLIC_KEY is not None and not PUBLIC_KEY == "":
        return PUBLIC_KEY
    url = concat_url(consts.SSO_URL, SSO_CERTS_ENDPOINT)
    # Make a GET request to the constructed URL
    resp = gateway(url, "GET")
    try:
        # Parse the response as JSON and filter the keys to find the one with algorithm "RS256"
        data = resp.json()
        data = [key for key in data["keys"] if key["alg"] == JWT_ALGORITHM][0]
        # Convert the selected key to RSA format and assign it to PUBLIC_KEY
        PUBLIC_KEY = rsa.from_jwk(json.dumps(data))
        return PUBLIC_KEY  # Return the PUBLIC_KEY
    except jwt.InvalidTokenError as i_e:
        log.error(i_e, exc_info=True)  # Log the error and abort with status code 401
        abort(401)
    except KeyError as k_e:
        log.error(k_e, exc_info=True)  # Log the error and abort with status code 502
        abort(502)
    except json.decoder.JSONDecodeError as j_e:
        log.error(j_e, exc_info=True)  # Log the error and abort with status code 502
        abort(502)


def get_header_role(request: Request) -> str:
    """
    Retrieve the role header from the request
    Log the role header value for debugging purposes
    Check if the role header exists and is not empty
    Return a set containing the role header
    """
    # Retrieve the role header from the request
    role_header: str = request.headers.get(X_AUTH_ROLE_HEADER)

    # Log the role header value for debugging purposes
    log.debug(f"x-auth-role is {role_header}")

    # Check if the role header exists and is not empty
    if role_header is None or len(role_header) == 0:
        # If it is empty or does not exist, abort the request with a 401 status code
        abort(401)

    # Return a set containing the role header
    return role_header


def get_header_account(request: Request) -> str:
    """
    Get the value of the x-auth-account header from the request.
    Log the value of the x-auth-account header.
    Check if the account_header is None or empty, if so, abort the request with a 401 status code.
    Return the value of the x-auth-account header.
    """

    # Get the value of the x-auth-account header from the request
    account_header: str = request.headers.get(X_AUTH_ACCOUNT_HEADER)

    # Log the value of the x-auth-account header
    log.debug(f"x-auth-account is {account_header}")

    # Check if the account_header is None or empty, if so, abort the request with a 401 status code
    if not account_header:
        abort(401)

    # Return the value of the x-auth-account header
    return account_header


def get_header_group(request: Request) -> str:
    """
    Retrieve the value of the "x-auth-group" header from the request.

    Returns:
        str: The value of the "x-auth-group" header.
    """
    # Retrieve the value of the "x-auth-group" header from the request.
    auth_header: str = request.headers.get(X_AUTH_GROUP_HEADER)

    # Log the value of the "x-auth-group" header for debugging purposes.
    log.debug(f"x-auth-group is {auth_header}")

    # Check if the "x-auth-group" header is None or empty, if so, return None.
    if not auth_header:
        log.debug("x-auth-group is missing or empty")
        return None
    # Split the header value by "." and return the result.
    return auth_header.split(".")


def permission(required_role: str) -> bool:
    """
    Check if the user has permission based on the required role.

    :param required_role: str, Role required to access the function
    :return: bool, True if the user has permission, False otherwise
    """

    # Attempt to get the auth group header
    auth_group_header = get_header_group(request)
    if auth_group_header:
        account, role = auth_group_header
    else:
        account = get_header_account(request)
        role = get_header_role(request)

    log.debug(f"account {account} role {role}")

    # Check if the role is valid and required
    if role not in valid_roles or role != required_role:
        log.debug(f"Invalid or mismatched role: {role}")
        return False

    # Assuming roles() returns a list or set of roles
    user_roles = set(roles(get_auth_info(), account))
    log.debug(f"user roles {user_roles}, required_role {required_role}")

    return role in user_roles


def account_auth_required(view):
    """
    Decorator to require account authentication for a view function.

    Parameters:
        view: function
            The view function to be wrapped.

    Returns:
        function
            The wrapped function with added authentication requirements.
    """

    @functools.wraps(view)
    def wrap(*args, **kwargs):
        """
        Wraps the given view function to require only JWT token for authentication.

        Parameters:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            The result of the original view function.
        """
        log.debug("Require only JWT token")

        auth_group_header = get_header_group(request)

        if auth_group_header is not None:
            account, role = get_header_group(request)

            # Check if the required role is valid
            if role not in valid_roles:
                log.debug(f"Invalid required role: {role}")
                abort(403)
        if auth_group_header is None:
            account = get_header_account(request)
            role = get_header_role(request)

            # Check if the required role is valid
            if role not in valid_roles:
                log.debug(f"Invalid required role: {role}")
                abort(403)

        if len(roles(get_auth_info(), account)) == 0:
            abort(403)
        kwargs["account_name"] = account
        kwargs["role"] = role
        kwargs["requester_id"] = get_auth_info()["user_id"]
        return view(*args, **kwargs)

    return wrap


def account_admin_required(view):
    """
    Decorator that requires the user to have an account admin role.
    """

    @functools.wraps(view)
    def wrap(*args, **kwargs):
        log.debug("Require account admin role")
        if not permission(ADMIN_ROLE):
            abort(403)
        return view(role=ADMIN_ROLE, *args, **kwargs)

    return wrap


def operator_required(view):
    """
    Decorator to require the account storage role for the given view function.
    """

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        """
        A wrapper function that checks for permission and then calls the original view function with a modified role parameter.
        """
        role = LOCATION_ADMIN_GROUP.split(".")[1]
        if not permission(role):
            abort(403)
        return view(role=role, *args, **kwargs)

    return wrapper


def filter_response(array, role, requester_id):
    """
    Filter the response based on the role of the requester.

    Args:
    array (list): The array of items to be filtered.
    role (str): The role of the requester.
    requester_id (int): The ID of the requester.

    Returns:
    list: The filtered array based on the role of the requester.
    """

    if role == MEMBER_ROLE:
        # Only return items owned by the requester
        return [i for i in array if i["owner"] == requester_id]
    elif role in PRIVELEGED_ROLES:
        # Return the entire array for admin, cloud, or operator roles
        return array
    else:
        # Return an empty array for unknown roles
        return []
