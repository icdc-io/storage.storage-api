from sqlalchemy.orm import joinedload
from flask import abort, jsonify
from marshmallow import ValidationError

from app.lib.request_utils import abort_detailed, log
from app.models.account import Accounts, AccountSchema
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from app.models.pool import Pools
from app import consts


def get_account_quotas(**kwargs):
    account_name = kwargs["account_name"]

    account = Accounts.query.filter_by(name=account_name).first()

    if account is None:
        abort(404, "Account with this name not found.")

    quotas = IscsiQuotas.query.filter_by(account_id=account.id).all()
    return jsonify(IscsiQuotaSchema(many=True).dump(quotas))


def create(**kwargs):
    body = kwargs["body"]
    account_name = body.pop("account_name")

    log.debug(f"Set iSCSI quota to account {account_name} with params {body}")

    account = Accounts.query.filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with name not found.")

    if IscsiQuotas.query.filter_by(account_id=account.id, pool_id=body["pool_id"]).first():
        abort(409, "Quota for this pool already exists.")

    try:
        IscsiQuotaSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    body |= {"account_id": account.id}
    quota = IscsiQuotas(**body)
    quota.save()
    return IscsiQuotaSchema().dump(quota)


def update(**kwargs):
    quota = IscsiQuotas.query.get(kwargs["id"])
    if not quota:
        abort(404, "Quota with this ID not found.")
    schema = IscsiQuotaSchema(context={"usage": quota.compute_usage()})
    try:
        schema.load(kwargs["body"] | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    quota.update(kwargs["body"])
    return IscsiQuotaSchema().dump(quota)


def destroy(**kwargs):
    quota = IscsiQuotas.query.get(kwargs["id"])
    if not quota:
        abort(404, "Quota with this ID not found.")
    quota.destroy()
    return jsonify("No content.")
