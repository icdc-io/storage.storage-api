import os
from flask_rbac_icdc import RBAC
from app.models.account import Accounts

rbac_config_path = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "../settings/rbac.yaml"
)

rbac = RBAC(rbac_config_path, Accounts, validate=True)
