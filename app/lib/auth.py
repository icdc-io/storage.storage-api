from enum import Enum
from functools import wraps

import requests
from flask import request, abort

from app.lib.request_utils import abort_detailed
from app.models.account import Accounts
from app import consts
RBAC_POLICY: dict = consts.ROLES
roles = {role.upper(): role for role in RBAC_POLICY.keys()}
Roles = Enum("Roles", roles)


class PermissionException(Exception):
    """
    Raised when subject trying to perform an
    operation without the access rights
    """

    def __init__(self, message):
        self.message = message
        super().__init__(message)


class Subject:
    def __init__(self, headers: dict, action: str):
        account = Accounts.get_by("name", headers.get("X-Auth-Account"))
        if not account:
            raise ValueError("Account name not found")
        role = Roles(headers.get("X-Auth-Role"))
        role = Roles("operator")
        operator = role.name == "operator"
        self.account = account
        self.account_id = account.id
        self.account_name = account.name
        self.role = role
        self.owner = headers.get("X-Auth-User")
        self.full_name = headers.get("X-Auth-User-Fullname")
        self.forwarded_for = headers.get("X-Forwarded-For")
        self.forwarded_host = headers.get("X-Forwarded-Host")
        requested_object, requested_permission = action.rsplit(".", 1)

        if not requested_object in RBAC_POLICY[role.value]:
            raise PermissionException(
                f"Access to {action} forbidden for role {role.name}"
            )
        self.requested_object = requested_object
        permissions = RBAC_POLICY[role.value][requested_object]["permissions"]
        if not requested_permission in permissions:
            raise PermissionException(
                f"Access to {action} forbidden for role {role.name}"
            )

        self.permissions = permissions
        self.filters = {
            key: getattr(self, value)
            for key, value in RBAC_POLICY[role.value][requested_object][
                "filters"
            ].items()
        }

    def __repr__(self):
        return (
            f"Subject(\n"
            f"  role={self.role},\n"
            f"  account_id={self.account.id},\n"
            f"  account_name={self.account.name},\n"
            f"  permissions={self.permissions},\n"
            f"  filters={self.filters}\n"
            f")"
        )

    def is_privileged_role(self):
        return self.role.name in ["admin", "owner", "operator"]

    def is_operator(self):
        return self.is_operator()

def rbac(action):
    def wrapper(func):
        @wraps(func)
        def wrap(*args, **kwargs):
            headers = request.headers
            try:
                subject = Subject(headers, action)
            except ValueError as e:
                abort(401, "Invalid auth parameters.")
            except PermissionException as e:
                abort(401, e.message)
            kwargs["subject"] = subject
            return func(*args, **kwargs)
        return wrap
    return wrapper
