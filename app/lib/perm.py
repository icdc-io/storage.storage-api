"""
Permission module
"""


def is_admin(role):
    return role in ["admin", "owner", "operator"]
