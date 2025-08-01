"""
This module provides authorization utilities
"""

import re
from app import consts


def is_operator(account, role) -> bool:
    """
    Check operator permissions
    """
    operator_group = consts.get("OPERATOR_GROUP")
    operator = re.split(r"[./]", operator_group)
    separator = "." if "." in operator_group else "/"
    return role == operator[-1] and account == separator.join(operator[:-1])
