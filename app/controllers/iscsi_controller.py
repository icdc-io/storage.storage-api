"""
iSCSI Controller
"""

import json
from datetime import datetime
from sqlite3 import IntegrityError

from flask import abort, jsonify
from app.controllers.auth import filter_response
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
    abort_detailed
)
from app.lib.perm import is_admin
from app.models.account import Accounts
from app.models.iscsi_quota import IscsiQuotas, IscsiQuotaSchema
from app.models.iscsi_client import IscsiClients, IscsiClientSchema
from app.models.iscsi_config import IscsiConfigs, IscsiConfigSchema
from app.models.iscsi_disk import IscsiDisks, IscsiDiskSchema
from app.models.iscsi_gateway import IscsiGateways
from app.models.pool import Pools
from app.models.snapshot import Snapshots
from app import consts


def get_iscsi_limits(subject):
    """
    List account's ISCSI per-pool limit-sets
    """
    default = Accounts.query.filter_by(name=consts.ACCOUNT_DEFAULT).first()
    limits = IscsiQuotas.query.filter_by(account_id=default.id).all()
    limits = [limit.toDict() for limit in limits]
    return jsonify(limits)


def set_iscsi_configs(**kwargs):
    """
    Store iSCSI config in Postgres
    """
    body = kwargs["body"]
    account_name = body.pop("account_name")
    log.debug(
        f"Set iSCSI config to account {account_name} with params {body}"
    )
    try:
        account = Accounts.query.filter_by(name=account_name).first()
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


def get_configs(**kwargs):
    """
    Get iSCSI configs from Postgres
    """
    account_name = kwargs["account_name"]
    account_obj = Accounts.query.filter_by(name=account_name).first()
    if not account_obj:
        return abort(404, "Account with such name does not exists.")
    return jsonify(IscsiConfigSchema(many=True).dump(account_obj.iscsi_configs))


def delete_config(**kwargs):
    """
    Delete iSCSI config
    """
    config_id = kwargs["config_id"]
    log.debug(f"Delete config with id {config_id}")
    config_obj = IscsiConfigs.get_by("id", config_id)
    if not config_obj:
        abort(404, "Config with this ID not found")
    config_obj.remove()
    return jsonify("No content.")


def get_config(**kwargs):
    """
    Get iSCSI Config
    """
    config_id = kwargs["config_id"]
    config = IscsiConfigs.get_by("id", config_id)
    if not config:
        abort(404, "Config with this ID not found")
    return IscsiConfigSchema().dump(config)


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


def get_config_disks(**kwargs):
    """
    Get all iSCSI disks which are assigned to config
    """
    config_id, role, requester_id = (
        kwargs["config_id"],
        kwargs["role"],
        kwargs["requester_id"],
    )
    config_obj = IscsiConfigs.get_by("id", config_id)
    if not config_obj:
        return not_found("Config with this ID not found.")
    return ok(
        filter_response(
            [IscsiDiskSchema().dump(disk) for disk in config_obj.disks], role, requester_id
        )
    )


def create_config_disk(**kwargs):
    """
    Create iSCSI disk and assign it to iSCSI Config
    """
    """
    Create iSCSI disk and assign it to iSCSI Config
    """
    config_id, body = kwargs["config_id"], kwargs["body"]
    log.debug(
        f"Create disk with params {body} and assign disk to config with id {config_id}"
    )
    config_obj = IscsiConfigs.get_by("id", config_id)
    if config_obj is None:
        return not_found("There is no config with such id.")
    gateway_obj = config_obj.gateways[0]
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    quotas = [
        quota for quota in account_obj.iscsi_quotas if quota.pool_id == pool_obj.id
    ]
    if len(quotas) == 0:
        return conflict("Account doesn't have quota for this pool")
    quota_obj = quotas[0]
    account_usage = [
        quota
        for quota in _get_iscsi_account_usage(account_obj)
        if quota["id"] == quota_obj.id
    ][0]

    check = _check_iscsi_account_quota(account_usage["stats"], body)
    if check is not True:
        return conflict(f"Quota overflow! {', '.join(check).capitalize()}.")

    response = Iscsi().create_disk(
        config=config_obj, gateway=gateway_obj, image=True, body=body
    )
    if is_failed(response):
        return status_codes.get(response["code"])(
            json.loads(response["data"])["message"]
        )
    return created(response)


# will be deprecated and replaced with iscsi/disks/<disk_id> update soon
def delete_config_disk(**kwargs):
    """
    Delete iSCSI Disk and disconnect it from Confi.
    Depends on clients which are assigned to this disk
    """
    """
    Delete iSCSI Disk and disconnect it from Confi.
    Depends on clients which are assigned to this disk
    """
    config_id, disk_id = kwargs["config_id"], kwargs["disk_id"]
    log.debug(f"Delete disk with id {disk_id}")
    config_obj = IscsiConfigs.get_by("id", config_id)
    if config_obj is None:
        return not_found("There is no config with such id.")
    gateway_obj = config_obj.gateways[0]
    disk_obj = IscsiDisks.get_by("id", disk_id)
    count_disk_clients = len(disk_obj.clients)
    if count_disk_clients != 0:
        return conflict(f"This disk is used by {count_disk_clients} clients")
        return conflict(f"This disk is used by {count_disk_clients} clients")

    if len(disk_obj.snapshots):
        return conflict("This disk cannot be deleted. Disk has snapshots.")

    response = Iscsi().delete_iscsi_disk(
        config=config_obj, gateway=gateway_obj, disk_name=disk_obj.name
    )
    if not is_failed(response):
        disk_obj.remove()
    return no_content(disk_obj.serialize())


def delete_disk(**kwargs):
    """
    Delete iSCSI Disk and disconnect it from Config.
    Depends on clients which are assigned to this disk
    """

    disk_id = kwargs["disk_id"]
    log.debug(f"Delete disk with id {disk_id}")
    disk = IscsiDisks.get_by("id", disk_id)
    if not disk:
        return not_found("There no disk with such id.")
    if len(disk.clients) != 0:
        return conflict(f"This disk is used by {len(disk.clients)} clients")
    if len(disk.snapshots):
        return conflict("This disk cannot be deleted. Disk has snapshots.")

    config = IscsiConfigs.get_by("id", disk.config_id)
    gateway = config.gateways[0]
    response = Iscsi().delete_iscsi_disk(
        config=config, gateway=gateway, disk_name=disk.name
    )
    if not is_failed(response):
        disk.remove()
    return no_content(IscsiDiskSchema().dump(disk))


def get_iscsi_clients(**kwargs):
    """
    Get list of iSCSI clients
    """
    account_name, role, requester_id = (
        kwargs["account_name"],
        kwargs["role"],
        kwargs["requester_id"],
    )
    account_obj = Accounts.query.filter_by(name=account_name).first()
    if not account_obj:
        abort(404, "Account with name not found.")
    clients = IscsiClientSchema(many=True).dump(account_obj.iscsi_clients)
    return jsonify(filter_response(clients, role, requester_id))


def create_iscsi_client(**kwargs):
    """
    Create iSCSI Client in Ceph and Postgres
    """
    body = kwargs["body"]
    account_name = body.pop("account_name")
    log.debug(
        f"Create iSCSI client to account {account_name} with params {body}"
    )
    try:
        account_obj = Accounts.query.filter_by(name=account_name).first()
        if not account_obj:
            abort(404, "Account with this name not found.")
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


def get_client_disks(**kwargs):
    """
    Get clients of disk. Depends on role of requester
    """
    client_id, role, requester_id = (
        kwargs["client_id"],
        kwargs["role"],
        kwargs["requester_id"],
    )
    client_obj = IscsiClients.get_by("id", client_id)
    if client_obj is None:
        return abort(404, "There is no client with such ID.")
    return jsonify(
        filter_response(
            [IscsiDiskSchema(exclude=['clients'], many=True).dump(client_obj.disks)],
            role,
            requester_id,
        )
    )


def disks_to_client(**kwargs):
    """
    Connect iSCSI disks to client
    """
    """
    Connect and disconnect iSCSI disks to client
    """
    client_id, body = kwargs["client_id"], kwargs["body"]
    client_obj = IscsiClients.get_by("id", client_id)
    if not client_obj:
        abort(404, "Client with this ID not found.")
    response = []
    for disk in body:
        response.append(_connect_disk(client_obj, disk))
    for i in response:
        if i['code'] == 409:
            abort_detailed(409, "Invalid parameters.", i['data'])
        elif i['code'] == 404:
            abort_detailed(404, "Disk not found.", i['data'])
        elif i['code'] == 500:
            abort(500, "Server error.")
    return jsonify(body)


def unassign_client_disk(**kwargs):
    """
    Disconnect iSCSI disks to client
    """
    client_id, disk_id = kwargs["client_id"], kwargs["disk_id"]
    client_obj = IscsiClients.get_by("id", client_id)
    if not client_obj:
        abort(404, "Client with this ID not found.")
    response = [_disconnect_disk(client_obj, disk_id)]
    for i in response:
        if i['code'] == 409:
            abort_detailed(409, "Invalid parameters.", i['data'])
        elif i['code'] == 404:
            abort_detailed(404, "Disk not found.", i['data'])
        elif i['code'] == 500:
            abort(500, "Server error.")
    return jsonify("No content.")


def _connect_disk(client_obj, disk):
    log.debug(f"Connect Disk {disk['id']} to clinet {client_obj.iqn}")
    disk_obj = IscsiDisks.get_by("id", disk["id"])
    if not disk_obj:
        return not_found("Disk with this ID does not exist.")
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    quota = [
        i
        for i in Accounts.get_by("id", config_obj.account_id).iscsi_quotas
        if i.pool_id == config_obj.pool_id
    ][0]
    gateway_obj = config_obj.gateways[0]
    clients = []
    for disk in config_obj.disks:
        for client in disk.clients:
            clients.append(client.id)
    if len(set(clients)) + 1 > quota.clients:
        return conflict("Clients quota overflow")
    return Iscsi().assign_disk(client_obj, disk_obj, config_obj, gateway_obj)


def _disconnect_disk(client_obj, disk_id):
    log.debug(f"Disconnect Disk {disk_id} to clinet {client_obj.iqn}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    if not disk_obj:
        return not_found("Disk with this ID does not exist.")
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    gateway_obj = config_obj.gateways[0]
    return Iscsi().disconnect_disk(client_obj, disk_obj, config_obj, gateway_obj)



def get_disk_snapshots(**kwargs):
    """
    Get list of snapshots which are assigned to disk
    """
    """
    Get list of snapshots which are assigned to disk
    """
    disk_id = kwargs["disk_id"]
    disk_obj = IscsiDisks.get_by("id", disk_id)
    return ok([snapshot.serialize() for snapshot in disk_obj.snapshots])


def create_disk_snapshot(**kwargs):
    """
    Create new snaphot on Ceph side and on Postgres side
    Assign Snapshot to Disk
    """
    disk_id, body = kwargs["disk_id"], kwargs["body"]
    log.debug(f"Create Snapshot based on disk {disk_id} with params {body}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    quota_obj = [
        quota for quota in account_obj.iscsi_quotas if quota.pool_id == pool_obj.id
    ][0]
    account_usage = [
        quota
        for quota in _get_iscsi_account_usage(account_obj)
        if quota["id"] == quota_obj.id
    ][0]
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    body["pool"], body["disk"] = f"{pool_obj.type}-{pool_obj.klass}", disk_name
    disk_params = disk_obj.serialize()
    disk_params["snapshots"] = 1
    disk_params["size_gb"] = 0

    check = _check_iscsi_account_quota(
        account_usage["stats"], disk_params, disk_count=0
    )
    if check is not True:
        return conflict(f"Quota overflow! {', '.join(check).capitalize()}.")

    response = Iscsi().create_snapshot(body=body)
    _ = [body.pop(key, None) for key in ["pool", "disk", "ioctx", "rbd", "image"]]
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    body["size_gb"] = response["size"] / 1024**3
    body["creation_time"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    body["disk_id"] = disk_id
    snapshot_obj = Snapshots(**body)
    snapshot_obj.save()
    return created(snapshot_obj.serialize())


def get_snapshot(**kwargs):
    """
    Get snapshot by id
    """
    disk_id, snapshot_name = kwargs["disk_id"], kwargs["snapshot_name"]
    disk_obj = IscsiDisks.get_by("id", disk_id)
    snapshots = [
        snapshot for snapshot in disk_obj.snapshots if snapshot.name == snapshot_name
    ]
    if len(snapshots) == 0:
        return not_found("Disk hasn't got snapshots")

    return ok(snapshots[0].serialize())


def update_snapshot(**kwargs):
    """
    Update snapshot description
    """
    disk_id, snapshot_name, body = (
        kwargs["disk_id"],
        kwargs["snapshot_name"],
        kwargs["body"],
    )
    log.debug(f"Update Snapshot {snapshot_name} with params {body}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    body["pool"], body["disk"], body["snapshot_name"] = (
        f"{pool_obj.type}-{pool_obj.klass}",
        disk_name,
        snapshot_name,
    )
    snapshots = [
        snapshot for snapshot in disk_obj.snapshots if snapshot.name == snapshot_name
    ]
    if len(snapshots) == 0:
        return not_found("Disk hasn't got snapshots")

    snapshot_obj = snapshots[0]
    if body["new_snapshot_name"] != snapshot_obj.name:
        response = Iscsi().update_snapshot(body=body)
        if is_failed(response):
            return status_codes.get(response["code"])(response["data"])

    snapshot_obj.update(body)
    return no_content()


def delete_snapshot(**kwargs):
    """
    Delete snapshot by name
    """
    disk_id, snapshot_name = kwargs["disk_id"], kwargs["snapshot_name"]
    log.debug(f"Delete snapshot {snapshot_name} from disk with id {disk_id}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    config_obj = IscsiConfigs.get_by("id", disk_obj.config_id)
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    disk_name = f"{account_obj.name}_{disk_obj.name}"
    kwargs["pool"], kwargs["disk"], kwargs["snapshot"] = (
        f"{pool_obj.type}-{pool_obj.klass}",
        disk_name,
        snapshot_name,
    )
    snapshots = [
        snapshot for snapshot in disk_obj.snapshots if snapshot.name == snapshot_name
    ]
    if len(snapshots) == 0:
        return not_found("Disk hasn't got the snapshot with such name.")

    response = Iscsi().delete_snapshot(body=kwargs)
    if is_failed(response):
        return status_codes.get(response["code"])(response["data"])

    snapshots[0].remove()
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


def delete_client(**kwargs):
    """
    Delete Client. Depends on Disks od this client
    """
    """
    Delete Client. Depends on Disks od this client
    """
    client_id = kwargs["client_id"]
    log.debug(f"Delete client with id {client_id}")
    client_obj = IscsiClients.get_by("id", client_id)
    if not client_obj:
        abort(404, "Client with this ID not found.")
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


def update_client(**kwargs):
    """
    Update Client. Depends on role of requester
    """
    """
    Update Client. Depends on role of requester
    """
    client_id, body, role = kwargs["client_id"], kwargs["body"], kwargs["role"]
    log.debug(f"Update client {client_id}")
    client_obj = IscsiClients.get_by("id", client_id)
    if not client_obj:
        abort(404, "Client with this ID not found.")
    if is_admin(role):
        body["owner"] = client_obj.owner  # pylint: disable=multiple-statements
    client_disks = client_obj.disks
    if not client_disks == []:
        for disk in client_disks:
            Iscsi().update_user(client_obj, disk, body)
    client_obj.update(body)
    return IscsiClientSchema().dump(client_obj)


# will be deprecated and replaced with iscsi/disks/<disk_id> update soon
@trytest
def update_disk_legacy(**kwargs):
    """
    Update disk. Resize disk can be only heigher than before resize
    """
    disk_id, config_id, role, body = (
        kwargs["disk_id"],
        kwargs["config_id"],
        kwargs["role"],
        kwargs["body"],
    )
    log.debug(f"Update disk {disk_id}. Mapped on config {config_id}. Params {body}")
    disk_obj = IscsiDisks.get_by("id", disk_id)
    config_obj = IscsiConfigs.get_by("id", config_id)
    account_obj = Accounts.get_by("id", config_obj.account_id)
    pool_obj = Pools.get_by("id", config_obj.pool_id)
    quota_obj = [
        quota for quota in account_obj.iscsi_quotas if quota.pool_id == pool_obj.id
    ][0]
    account_usage = [
        quota
        for quota in _get_iscsi_account_usage(account_obj)
        if quota["id"] == quota_obj.id
    ][0]
    check = _check_iscsi_account_quota_disk_update(
        account_usage["stats"], body, disk_obj
    )
    if check is not True:
        return conflict(f"Quota overflow! {', '.join(check).capitalize()}.")

    if "size_gb" in body:
        if body["size_gb"] > disk_obj.size_gb:
            response = Iscsi().update_disk(disk_obj, config_obj, body)
            if is_failed(response):
                return status_codes.get(response["code"])(
                    json.loads(response["data"])["message"]
                )
    if role != "admin":
        body["owner"] = disk_obj.owner  # pylint: disable=multiple-statements
    disk_obj.update(body)
    return no_content()


@trytest
def update_disk(**kwargs):
    """
    Update disk. Resize disk can be only heigher than before resize
    """
    disk_id, role, body = (
        kwargs['disk_id'],
        kwargs['role'],
        kwargs['body']
    )
    disk = IscsiDisks.get_by('id', disk_id)
    config = IscsiConfigs.get_by('id', disk.config_id)
    if not disk:
        return not_found("Disk with this ID not found")

    schema = IscsiDiskSchema(
        context={
            'disk': disk,
            'config': config
        }
    )
    errors = schema.validate(body)
    if errors:
        return unprocessable_entity(errors)

    if "size_gb" in body:
        if body["size_gb"] > disk.size_gb:
            response = Iscsi().update_disk(disk, config, body)
            if is_failed(response):
                return status_codes.get(response["code"])(
                    json.loads(response["data"])["message"]
                )
        else:
            return unprocessable_entity("Resize disk must be higher than previous size.")

    if is_admin(role):
        body['owner'] = disk.owner  # pylint: disable=multiple-statements
    disk.update(kwargs['body'])
    return ok(IscsiDiskSchema().dump(disk))


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
