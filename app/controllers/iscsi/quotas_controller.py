from flask import abort, jsonify, request
from marshmallow import ValidationError
from sqlalchemy.orm import selectinload

from app.lib.request_utils import (
    abort_detailed,
    log,
    parse_jsonapi_filters,
    request_json,
)
from app.models.account import Accounts
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema


def get_account_quotas(subject):
    schema = IscsiQuotaSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except ValidationError as e:
        abort_detailed(400, "Invalid query parameters.", e.messages)
    quotas = IscsiQuotas.filtered(subject).options(selectinload(IscsiQuotas.pool)) \
             .filter_by(**filters).except_(IscsiQuotas.get_default_limitsets()).all()
    return jsonify(IscsiQuotaSchema(many=True).dump(quotas))


def create(subject, body=None):
    if not body:
        body = request_json(request)
    account_name = body.pop("account_name")
    log.debug(f"Set iSCSI quota to account {account_name} with params {body}")

    account = Accounts.filtered(subject).filter_by(name=account_name).first()
    if not account:
        abort(404, "Account with this name not found.")

    if IscsiQuotas.query.filter_by(account_id=account.id, pool_id=body["pool_id"]).first():
        abort(409, "Quota for this pool already exists.")
    try:
        validated_body = IscsiQuotaSchema().load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    validated_body |= {"account_id": account.id}
    quota = IscsiQuotas(**validated_body)
    quota.save()
    return IscsiQuotaSchema().dump(quota)


def update(subject, quota_id):
    body = request_json(request)
    quota = IscsiQuotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    schema = IscsiQuotaSchema(context={"usage": quota.compute_usage()})
    try:
        validated_body = schema.load(body | {"pool_id": quota.pool_id})
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    quota.update(validated_body)
    return IscsiQuotaSchema().dump(quota)


def destroy(subject, quota_id):
    quota = IscsiQuotas.filtered(subject).filter_by(id=quota_id).first()
    if not quota:
        abort(404, "Quota with this ID not found or you haven't access for it.")
    quota.destroy()
    return jsonify("No content.")
