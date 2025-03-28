"""
iSCSI Controller
"""

import json
from datetime import datetime
from sqlite3 import IntegrityError
from flask import abort, jsonify, request
from marshmallow import ValidationError
from app.lib.controller_utils import (
    _check_iscsi_account_quota,
    _check_iscsi_account_quota_disk_update,
    _get_iscsi_account_usage,
    status_codes,
    trytest,
)
from app.lib.iscsi_utils import Iscsi
from app.lib.request_utils import (
    conflict,
    created,
    is_failed,
    log,
    no_content,
    not_found,
    ok,
    unprocessable_entity,
    abort_detailed, request_json, parse_jsonapi_filters
)
from app.lib.perm import is_admin
from app.models.account import Accounts
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from app.models.iscsi_client import IscsiClients, IscsiClientSchema
from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema
from app.models.iscsi_disk import IscsiDisks, IscsiDiskSchema
from app.models.iscsi_gateway import IscsiGateways
from app.models.pool import Pools
from app.models.snapshot import Snapshots, SnapshotSchema
from app import consts


def get_iscsi_limits(subject):
    """
    List account's ISCSI per-pool limit-sets
    """
    default = Accounts.query.filter_by(name=consts.ACCOUNT_DEFAULT).first()
    limits = IscsiQuotas.query.filter_by(account_id=default.id).all()
    limits = [limit.toDict() for limit in limits]
    return jsonify(limits)


def set_iscsi_configs(subject):
    """
    Store iSCSI config in Postgres
    """
    body = request_json(request)
    account_name = body.pop("account_name")
    log.debug(
        f"Set iSCSI config to account {account_name} with params {body}"
    )
    try:
        account = Accounts.filtered(subject).filter_by(name=account_name).first()
        if not account:
            abort(404, "Account with this name not found.")
        if IscsiConfigs.query.filter_by(account_id=account.id, pool_id=body["pool_id"]).first():
            abort(409, "Config for this pool already exist.")
        body["account_id"] = account.id
        config = IscsiConfigs(**body)
        config.save()
        if not config.id:
            abort(400, "Invalid parameters.")
        return IscsiConfigSchema().dump(config)
    except TypeError as e:
        abort(400, "Invalid parameters")


def get_configs(subject):
    """
    Get iSCSI configs from Postgres
    """
    schema = IscsiConfigSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except TypeError as e:
        abort(400, "Invalid query parameters.")
    configs = IscsiConfigs.filtered(subject).filter_by(**filters).all()
    return jsonify(IscsiConfigSchema(many=True).dump(configs))


def delete_config(subject, config_id):
    """
    Delete iSCSI config
    """
    log.debug(f"Delete config with id {config_id}")
    config_obj = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config_obj:
        abort(404, "Config with this ID not found or you have not permission.")
    config_obj.remove()
    return jsonify("No content.")


def get_config(subject, config_id):
    """
    Get iSCSI Config
    """
    config_obj = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if not config_obj:
        abort(404, "Config with this ID not found or you have not permission.")
    return IscsiConfigSchema().dump(config_obj)


@trytest
def set_iscsi_config(**kwargs):
    """
    Assign iSCSI gateway to config
    """
    """
    Assign iSCSI gateway to config
    """
    gateway_id, body = kwargs["gateway_id"], kwargs["body"]
    config_obj = IscsiConfigs(**body).save()
    gateway_obj = IscsiGateways.get_by("id", gateway_id)
    gateway_obj.configs.append(config_obj)
    gateway_obj.save()
    return ok(gateway_obj.serialize())


@trytest
def get_iscsi_configs(**kwargs):
    """
    Get iSCSI Configs
    """
    """
    Get iSCSI Configs
    """
    gateway_id = kwargs["gateway_id"]
    return ok([i.serialize() for i in IscsiGateways.get_by("id", gateway_id).configs])


@trytest
def set_iscsi_gateway(**kwargs):
    """
    Create and assign iSCSI Gateway to Account
    """
    """
    Create and assign iSCSI Gateway to Account
    """
    account_name, body = kwargs["account_name"], kwargs["body"]
    log.debug(
        f"Create and assign iSCSI gateway to account {account_name} with params {body}"
    )
    account_obj = Accounts.get_by("name", account_name)
    body["account_id"] = account_obj.id
    gateway = IscsiGateways(**body).save()
    return ok(gateway.serialize())


@trytest
def get_iscsi_gateways(**kwargs):
    """
    Get iSCSI Gateways
    """
    """
    Get iSCSI Gateways
    """
    account_name = kwargs["account_name"]
    account_obj = Accounts.get_by("name", account_name)
    return ok([i.serialize() for i in account_obj.iscsi_gateways])


def get_config_gateways(**kwargs):
    """
    Get iSCSI Config Gateways
    """
    """
    Get iSCSI Config Gateways
    """
    config_id = kwargs["config_id"]
    config_obj = IscsiConfigs.get_by("id", config_id)
    response = []
    for gateway in config_obj.gateways:
        gateway = gateway.serialize()
        gateway["account"] = Accounts.get_by("id", config_obj.account_id).serialize(
            ["quotas"]
        )
        response.append(gateway)
    return ok(response)


def get_config_disks(subject, config_id):
    """
    Get all iSCSI disks which are assigned to config
    """
    disks = IscsiDisks.filtered(subject).filter_by(config_id=config_id).all()
    return jsonify(IscsiDiskSchema(many=True).dump(disks))


def create_config_disk(subject, config_id):
    """
    Create iSCSI disk and assign it to iSCSI Config
    """
    body = request_json(request)
    log.debug(
        f"Create disk with params {body} and assign disk to config with id {config_id}"
    )
    config = IscsiConfigs.filtered(subject).filter_by(id=config_id).first()
    if config is None:
        abort(400, "There is no config with such id or you haven't permission or you haven't permission.")

    quota = IscsiQuotas.query.filter_by(account_id=config.account_id, pool_id=config.pool_id).first()
    if not quota:
        abort(400, "Account doesn't have quota for this pool")
    try:
        IscsiDiskSchema(context={
            "quota": quota
        }).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    gateway = config.gateways[0]
    if not gateway:
        abort(400, "You haven't gateway for this config.")
    response = Iscsi().create_disk(
        config=config, gateway=gateway, image=True, body=body
    )
    if is_failed(response):
        abort(response["code"], json.loads(response["data"])["message"])
    disk = response.get("data")
    return IscsiDiskSchema().dump(disk)


def update_disk(subject, disk_id):
    """
    Update disk. Resize disk can be only heigher than before resize
    """
    body = request_json(request)

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    config = IscsiConfigs.filtered(subject).filter_by(id=disk.config_id).first()
    if not config:
        abort(404, "Config with this ID not found or you haven't permission.")
    try:
        IscsiDiskSchema(
            context={
                'disk': disk,
                'config': config
            }
        ).load(body)
    except ValidationError as e:
        abort_detailed(400, "Invalid parameters.", e.messages)

    if "size_gb" in body:
        if body["size_gb"] > disk.size_gb:
            response = Iscsi().update_disk(disk, config, body)
            if is_failed(response):
                abort(response["code"], json.loads(response["data"])["message"])
        else:
            return abort(400, "Resize disk must be higher than previous size.")

    if not subject.is_privileged_role():
        body['owner'] = disk.owner  # pylint: disable=multiple-statements
    disk.update(body)
    return IscsiDiskSchema().dump(disk)


def delete_disk(subject, disk_id):
    """
    Delete iSCSI Disk and disconnect it from Config.
    Depends on clients which are assigned to this disk
    """

    log.debug(f"Delete disk with id {disk_id}")

    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "There no disk with such id or you haven't permission.")
    if len(disk.clients) != 0:
        abort(409, f"This disk is used by {len(disk.clients)} clients")
    if len(disk.snapshots):
        abort(409, "This disk cannot be deleted. Disk has snapshots.")
    disk.remove()
    return IscsiDiskSchema().dump(disk)


def get_iscsi_clients(subject):
    """
    Get list of iSCSI clients
    """
    schema = IscsiClientSchema(partial=True)
    parsed_filters = parse_jsonapi_filters(request.args)
    try:
        filters = schema.load(parsed_filters)
    except TypeError as e:
        abort(400, "Invalid query parameters.")
    clients = IscsiClients.filtered(subject).filter_by(**filters).all()
    return jsonify(IscsiClientSchema(many=True).dump(clients))


def create_iscsi_client(subject):
    """
    Create iSCSI Client in Ceph and Postgres
    """
    body = request_json(request)
    account_name = body.pop("account_name")
    log.debug(
        f"Create iSCSI client to account {account_name} with params {body}"
    )
    try:
        account_obj = Accounts.filtered(subject).filter_by(name=account_name).first()
        if not account_obj:
            abort(404, "Account with this name not found or you haven't permission.")
        body["account_id"] = account_obj.id
        client = IscsiClients(**body)
        client.save()
        if client.id is None:
            abort(409, "Can not create client with such IQN")
        return IscsiClientSchema().dump(client)
    except TypeError as exception:
        abort_detailed(400, f"Payload is not valid.", str(exception))
    except IntegrityError:
        abort(409, "Client with such iqn is already exists")


def get_client_disks(subject, client_id):
    """
    Get clients of disk. Depends on role of requester
    """
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if client_obj is None:
        return abort(404, "There is no client with such ID.")
    return jsonify(IscsiDiskSchema(many=True).dump(client_obj.disks))


def disks_to_client(subject, client_id):
    """
    Connect iSCSI disks to client
    """
    body = request_json(request)
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client_obj:
        abort(404, "Client with this ID not found or you haven't permission.")
    response = []
    for disk in body:
        response.append(_connect_disk(subject, client_obj, disk))
    for i in response:
        if i['code'] == 409:
            abort_detailed(409, "Invalid parameters.", i['data'])
        elif i['code'] == 404:
            abort_detailed(404, "Disk not found.", i['data'])
        elif i['code'] == 500:
            abort(500, "Server error.")
    return jsonify(body)


def unassign_client_disk(subject, client_id, disk_id):
    """
    Disconnect iSCSI disks to client
    """
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client_obj:
        abort(404, "Client with this ID not found or you haven't permission.")
    response = _disconnect_disk(subject, client_obj, disk_id)
    data = response.get("data", {})
    message = json.loads(data).get("message") if isinstance(data, bytes) else data
    if response['code'] == 400:
        abort_detailed(400, "Disk not mapped to client", message)
    elif response['code'] == 409:
        abort_detailed(409, "Invalid parameters.", message)
    elif response['code'] == 404:
        abort_detailed(404, "Disk not found.", message)
    elif response['code'] == 500:
        abort(500, "Server error.")
    disk_obj = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    client_obj.disks.remove(disk_obj)
    client_obj.save()
    return jsonify("No content.")


def _connect_disk(subject, client_obj, disk):
    log.debug(f"Connect Disk {disk['id']} to clinet {client_obj.iqn}")
    disk_obj = IscsiDisks.filtered(subject).filter_by(id=disk["id"]).first()
    if not disk_obj:
        abort(404, "Disk with this ID does not exist or you haven't permission")
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    quota = IscsiQuotas.query.filter_by(account_id=config_obj.account_id, pool_id=config_obj.pool_id).first()
    gateway_obj = config_obj.gateways[0]
    usage = quota.compute_usage()
    if usage["clients"] + 1 > quota.clients:
        abort(409, "Quota overflow for clients.")
    return Iscsi().assign_disk(client_obj, disk_obj, config_obj, gateway_obj)


def _disconnect_disk(subject, client_obj, disk_id):
    log.debug(f"Disconnect Disk {disk_id} to clinet {client_obj.iqn}")
    disk_obj = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk_obj:
        abort(404, "Disk with this ID does not exist or you haven't permission.")
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    gateway_obj = config_obj.gateways[0]
    return Iscsi().disconnect_disk(client_obj, disk_obj, config_obj, gateway_obj)



def get_disk_snapshots(subject, disk_id):
    """
    Get list of snapshots which are assigned to disk
    """
    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    return jsonify(SnapshotSchema(many=True).dump(disk.snapshots))


def create_disk_snapshot(subject, disk_id):
    """
    Create new snaphot on Ceph side and on Postgres side
    Assign Snapshot to Disk
    """
    body = request_json(request)
    log.debug(f"Create Snapshot based on disk {disk_id} with params {body}")
    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    config = IscsiConfigs.filtered(subject).filter_by(id=disk.config_id).first()
    account = Accounts.query.filter_by(id=config.account_id).first()
    pool = Pools.query.filter_by(id=config.pool_id).first()
    quota = IscsiQuotas.query.filter_by(pool_id=pool.id, account_id=account.id).first()
    disk_name = f"{account.name}_{disk.name}"
    body["pool"], body["disk"] = f"{pool.type}-{pool.klass}", disk_name
    disk_params = disk.serialize()
    disk_params["snapshots"] = 1
    disk_params["size_gb"] = 0
    usage = quota.compute_usage()
    if usage["snapshots"] + 1 > quota.snapshots:
        abort(409, "Quota overflow for snapshots!")

    response = Iscsi().create_snapshot(body=body)
    _ = [body.pop(key, None) for key in ["pool", "disk", "ioctx", "rbd", "image"]]
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    body["size_gb"] = response["size"] / 1024**3
    body["creation_time"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    body["disk_id"] = disk_id
    snapshot_obj = Snapshots(**body)
    snapshot_obj.save()
    return snapshot_obj.serialize()


def get_snapshot(subject, disk_id, snapshot_id):
    """
    Get snapshot by id
    """
    disk = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk:
        abort(404, "Disk not found or you haven't permission.")
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        return abort(404, "Disk hasn't got snapshots")

    return SnapshotSchema().dump(snapshot)


def update_snapshot(subject, disk_id, snapshot_id):
    """
    Update snapshot description
    """
    body = request_json(request)
    disk_obj = IscsiDisks.filtered(subject).filter_by(id=disk_id).first()
    if not disk_obj:
        abort(404, "Disk not found or you haven't permission.")
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot not found.")
    log.debug(f"Update Snapshot {snapshot.name} with params {body}")
    body["pool"], body["disk"], body["snapshot_name"] = (
        f"{pool_obj.type}-{pool_obj.klass}",
        disk_name,
        snapshot.name,
    )

    if body["new_snapshot_name"] != snapshot.name:
        response = Iscsi().update_snapshot(body=body)
        if is_failed(response):
            abort(response["code"], json.loads(response["data"])["message"])

    snapshot.update(body)
    return no_content()


def delete_snapshot(subject, disk_id, snapshot_id):
    """
    Delete snapshot by name
    """
    snapshot = Snapshots.filtered(subject).filter_by(id=snapshot_id).first()
    if not snapshot:
        abort(404, "Snapshot with this ID not found.")
    log.debug(f"Delete snapshot {snapshot.name} from disk with id {disk_id}")
    snapshot.remove()
    return no_content()


def new_disk_from_snapshot(**kwargs):
    """
    Create disk from snapshot
    """
    disk_id, snapshot_name, body = (
        kwargs["disk_id"],
        kwargs["snapshot_name"],
        kwargs["body"],
    )
    log.debug(f"Create new Disk based on disk {disk_id}, snapshot {snapshot_name}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    gateway_obj = config_obj.gateways[0]
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    (
        body["pool"],
        body["disk"],
        body["snapshot"],
        body["gateway"],
        body["config"],
        body["account_name"],
    ) = (
        f"{pool_obj.type}-{pool_obj.klass}",
        disk_name,
        snapshot_name,
        gateway_obj,
        config_obj,
        account_obj.name,
    )
    snapshots = [
        snapshot for snapshot in disk_obj.snapshots if snapshot.name == snapshot_name
    ]
    if len(snapshots) == 0:
        return not_found("Disk hasn't got the snapshot with such name.")

    quota_obj = [
        quota for quota in account_obj.iscsi_quotas if quota.pool_id == pool_obj.id
    ][0]
    account_usage = [
        quota
        for quota in _get_iscsi_account_usage(account_obj)
        if quota["id"] == quota_obj.id
    ][0]
    snapshot_obj = snapshots[0].serialize()
    snapshot_obj["snapshots"] = 0
    check = _check_iscsi_account_quota(account_usage["stats"], snapshot_obj)
    if check is not True:
        return conflict(f"Quota overflow! {', '.join(check).capitalize()}.")

    body["snapshot_params"] = snapshot_obj
    body["config_id"] = disk_obj.config_id
    response = Iscsi().new_disk_from_snapshot(body=body)
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    return created(response["data"].serialize())


def rollback_snapshot(**kwargs):
    """
    Rollback disk to snapshot
    """
    disk_id, snapshot_name, body = (
        kwargs["disk_id"],
        kwargs["snapshot_name"],
        kwargs["body"],
    )
    log.debug(f"Rollback disk {disk_id} to snapshot {snapshot_name}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    snapshot_obj = [snap for snap in disk_obj.snapshots if snap.name == snapshot_name]
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    gateway_obj = config_obj.gateways[0]
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    (
        body["pool"],
        body["disk"],
        body["snapshot"],
        body["gateway"],
        body["config"],
        body["account_name"],
    ) = (
        f"{pool_obj.type}-{pool_obj.klass}",
        disk_name,
        snapshot_name,
        gateway_obj,
        config_obj,
        account_obj.name,
    )
    snapshots = [
        snapshot for snapshot in disk_obj.snapshots if snapshot.name == snapshot_name
    ]
    if len(snapshots) == 0:
        return not_found("Disk hasn't got the snapshot with such name.")

    quota_obj = [
        quota for quota in account_obj.iscsi_quotas if quota.pool_id == pool_obj.id
    ][0]
    account_usage = [
        quota
        for quota in _get_iscsi_account_usage(account_obj)
        if quota["id"] == quota_obj.id
    ][0]
    snapshot_obj = snapshots[0].serialize()
    snapshot_obj["snapshots"] = 0
    check = _check_iscsi_account_quota(account_usage["stats"], snapshot_obj)
    if check is not True:
        return conflict(f"Quota overflow! {', '.join(check).capitalize()}.")

    body["snapshot_params"] = snapshot_obj
    body["config_id"] = disk_obj.config_id
    response = Iscsi().rollback_snapshot(body=body)
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])
    update_params = {"size_gb": response["data"] / 1024**3}
    disk_obj.update(update_params)
    return ok(disk_obj.serialize())


def delete_client(subject, client_id):
    """
    Delete Client. Depends on Disks od this client
    """
    log.debug(f"Delete client with id {client_id}")
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client_obj:
        abort(404, "Client with this ID not found or you haven't permission.")
    assigned_disks = len(client_obj.disks)
    if assigned_disks:
        abort(
            409,
            (
                f"Client assigned to {assigned_disks} disks. "
                "Unassign disks before deleting client."
            )
        )
    client_obj.remove()
    return jsonify("No content.")


def update_client(subject, client_id):
    """
    Update Client. Depends on role of requester
    """
    body = request_json(request)
    log.debug(f"Update client {client_id}")
    client_obj = IscsiClients.filtered(subject).filter_by(id=client_id).first()
    if not client_obj:
        abort(404, "Client with this ID not found or you haven't permission.")
    if not subject.is_privileged_role():
        body["owner"] = client_obj.owner  # pylint: disable=multiple-statements
    client_disks = client_obj.disks
    if not client_disks == []:
        for disk in client_disks:
            Iscsi().update_client(client_obj, disk, body)
    client_obj.update(body)
    return IscsiClientSchema().dump(client_obj)


def _disk_migrate(body):
    disk = IscsiDisks(**body)
    disk.save()
    return disk.serialize()


def _snapshot_migrate(body):
    snapshot = Snapshots(**body)
    snapshot.save()
    return snapshot.serialize()


def _migrate_assigned_disks(clinet, disk):
    client_obj = IscsiClients.get_by("id", clinet["id"])
    disk_obj = IscsiDisks.get_by("name", disk["disk_name"])
    assigned_disks = client_obj.disks
    assigned_disks.append(disk_obj)
    client_obj.save()
