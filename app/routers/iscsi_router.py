"""
iSCSI Router module
"""
from flask import Blueprint, request

from app.controllers import iscsi_controller as controller
from app.lib.request_utils import process_response, request_json, handle_exception
from app.controllers.iscsi import quotas_controller
from app.lib import auth as auth
from werkzeug.exceptions import HTTPException

iscsi = Blueprint(name="iscsi", import_name=__name__)
iscsi.register_error_handler(HTTPException, handle_exception)


@iscsi.route("/limits", methods=["GET"])
@auth.rbac("iscsi.limits.list")
def get_iscsi_limits(subject):
    return controller.get_iscsi_limits(subject), 200


@iscsi.route("/quotas", methods=["GET"])
@auth.rbac("iscsi.quotas.list")
def get_account_iscsi_quota(subject):
    return quotas_controller.get_account_quotas(subject), 200


@iscsi.route("/quotas", methods=["POST"])
@auth.rbac("iscsi.quotas.create")
def set_account_iscsi_quota(subject):
    return quotas_controller.create(subject), 201


@iscsi.route("/quotas/<quota_id>", methods=["PUT"])
@auth.rbac("iscsi.quotas.update")
def update_iscsi_quota(subject, quota_id):
    return quotas_controller.update(subject, quota_id), 200


@iscsi.route("/quotas/<quota_id>", methods=["DELETE"])
@auth.rbac("iscsi.quotas.delete")
def destroy_iscsi_quota(subject, quota_id):
    return quotas_controller.destroy(subject, quota_id), 204


@iscsi.route("/configs", methods=["POST"])
@auth.rbac("iscsi.configs.create")
def create_iscsi_config(subject):
    return controller.set_iscsi_configs(subject), 201


@iscsi.route("/configs", methods=["GET"])
@auth.rbac("iscsi.configs.list")
def get_iscsi_configs(subject):
    return controller.get_configs(subject), 200


@iscsi.route("/configs/<config_id>", methods=["GET"])
@auth.rbac("iscsi.configs.get")
def get_config(subject, config_id):
    return controller.get_config(subject, config_id), 200


@iscsi.route("/configs/<config_id>", methods=["DELETE"])
@auth.rbac("iscsi.configs.delete")
def delete_config(subject, config_id):
    return controller.delete_config(subject, config_id), 204


@iscsi.route("/configs/<config_id>/gateways", methods=["GET"])
@auth.rbac("iscsi.gateways.list")
def get_config_gateways(subject, config_id):
    return controller.get_config_gateways(subject, config_id)


@iscsi.route("/configs/<config_id>/gateways", methods=["POST"])
@auth.rbac("iscsi.gateways.create")
def set_gateway(subject, config_id):
    return controller.set_config_gateway(subject, config_id)


@iscsi.route("/configs/<config_id>/disks", methods=["GET"])
@auth.rbac("iscsi.disks.list")
def get_config_disks(subject, config_id):
    return controller.get_config_disks(subject, config_id), 200


@iscsi.route("/configs/<config_id>/disks", methods=["POST"])
@auth.rbac("iscsi.disks.create")
def create_disk(subject, config_id):
    return controller.create_disk(subject, config_id), 201


@iscsi.route("/disks/<disk_id>", methods=["DELETE"])
@auth.rbac("iscsi.disks.delete")
def delete_disk(subject, disk_id):
    return controller.delete_disk(subject, disk_id), 204


@iscsi.route("/disks/<disk_id>", methods=["PUT"])
@auth.rbac("iscsi.disks.update")
def update_disk(subject, disk_id):
    return controller.update_disk(subject, disk_id), 200


@iscsi.route("/clients", methods=["POST"])
@auth.rbac("iscsi.clients.create")
def create_iscsi_client(subject):
    return controller.create_iscsi_client(subject), 201


@iscsi.route("/clients", methods=["GET"])
@auth.rbac("iscsi.clients.list")
def get_iscsi_clients(subject):
    return controller.get_iscsi_clients(subject), 200


@iscsi.route("/clients/<client_id>", methods=["DELETE"])
@auth.rbac("iscsi.clients.delete")
def delete_client(subject, client_id):
    return controller.delete_client(subject, client_id), 204


@iscsi.route("/clients/<client_id>", methods=["PUT"])
@auth.rbac("iscsi.clients.update")
def update_client(subject, client_id):
    return controller.update_client(subject, client_id), 200


@iscsi.route("/clients/<client_id>/disks", methods=["POST"])
@auth.rbac("iscsi.disks.assign")
def disks_to_client(subject, client_id):
    return controller.disks_to_client(subject, client_id), 201


@iscsi.route("/clients/<client_id>/disks/<disk_id>", methods=["DELETE"])
@auth.rbac("iscsi.disks.unassign")
def unassign_client_disk(subject, client_id, disk_id):
    return controller.unassign_client_disk(subject, client_id, disk_id), 204


@iscsi.route("/clients/<client_id>/disks", methods=["GET"])
@auth.rbac("iscsi.disks.list")
def get_client_disks(subject, client_id):
    return controller.get_client_disks(subject, client_id), 200


@iscsi.route("/disks/<disk_id>/snapshots", methods=["GET"])
@auth.rbac("iscsi.snapshots.list")
def get_disk_snapshots(subject, disk_id):
    return controller.get_disk_snapshots(subject, disk_id), 200


@iscsi.route("/disks/<disk_id>/snapshots", methods=["POST"])
@auth.rbac("iscsi.snapshots.create")
def create_disk_snapshot(subject, disk_id):
    return controller.create_disk_snapshot(subject, disk_id), 201


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_id>", methods=["GET"])
@auth.rbac("iscsi.snapshots.get")
def get_snapshot(subject, disk_id, snapshot_id):
    return controller.get_snapshot(subject, disk_id, snapshot_id), 200


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_id>", methods=["PUT"])
@auth.rbac("iscsi.snapshots.update")
def update_snapshot(subject, disk_id, snapshot_id):
    return controller.update_snapshot(subject, disk_id, snapshot_id), 200


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_id>", methods=["DELETE"])
@auth.rbac("iscsi.snapshots.delete")
def delete_snapshot(subject, disk_id, snapshot_id):
    return controller.delete_snapshot(subject, disk_id, snapshot_id), 204


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>/new_disk", methods=["POST"])
@auth.rbac("iscsi.disks.from-snapshot")
def new_disk_from_snapshot(subject, disk_id, snapshot_name):
    return controller.new_disk_from_snapshot(subject, disk_id, snapshot_name)


@iscsi.route("/disks/<disk_id>/snapshots/<snapshot_name>/rollback", methods=["POST"])
@auth.rbac("iscsi.snapshots.rollback")
def rollback_snapshot(subject, disk_id, snapshot_name):
    return controller.rollback_snapshot(subject, disk_id, snapshot_name)
