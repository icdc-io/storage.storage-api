"""
iSCSI Router module
"""
from flask import Blueprint
from werkzeug.exceptions import HTTPException

from app.controllers import iscsi_controller as controller
from app.controllers.iscsi import quotas_controller
from app.lib.request_utils import handle_exception
from app.rbac import rbac

iscsi = Blueprint(name="iscsi", import_name=__name__)
iscsi.register_error_handler(HTTPException, handle_exception)


@iscsi.route("/limits", methods=["GET"])
@rbac.allow("iscsi.limits.list")
def get_iscsi_limits(subject):
    return controller.get_iscsi_limits(subject), 200


@iscsi.route("/quotas", methods=["GET"])
@rbac.allow("iscsi.quotas.list")
def get_account_iscsi_quota(subject):
    return quotas_controller.get_account_quotas(subject), 200


@iscsi.route("/quotas", methods=["POST"])
@rbac.allow("iscsi.quotas.create")
def set_account_iscsi_quota(subject):
    return quotas_controller.create(subject), 201


@iscsi.route("/quotas/<quota_id>", methods=["PUT"])
@rbac.allow("iscsi.quotas.update")
def update_iscsi_quota(subject, quota_id):
    return quotas_controller.update(subject, quota_id), 200


@iscsi.route("/quotas/<quota_id>", methods=["DELETE"])
@rbac.allow("iscsi.quotas.delete")
def destroy_iscsi_quota(subject, quota_id):
    return quotas_controller.destroy(subject, quota_id), 204


@iscsi.route("/clusters", methods=["GET"])
@rbac.allow("iscsi.clusters.list")
def list_clusters(subject):
    return controller.get_clusters(subject), 200


@iscsi.route("/clusters", methods=["POST"])
@rbac.allow("iscsi.clusters.create")
def create_cluster(subject):
    return controller.create_cluster(subject), 201


@iscsi.route("/clusters/<cluster_id>", methods=["GET"])
@rbac.allow("iscsi.clusters.get")
def get_cluster(subject, cluster_id):
    return controller.get_cluster(subject, cluster_id), 200


@iscsi.route("/clusters/<cluster_id>", methods=["DELETE"])
@rbac.allow("iscsi.clusters.delete")
def delete_cluster(subject, cluster_id):
    return controller.delete_cluster(subject, cluster_id), 204


@iscsi.route("/targets", methods=["POST"])
@rbac.allow("iscsi.targets.create")
def create_target(subject):
    return controller.create_target(subject), 204


@iscsi.route("/targets/<target_id>", methods=["DELETE"])
@rbac.allow("iscsi.targets.delete")
def delete_target(subject, target_id):
    return controller.delete_target(subject, target_id), 204


@iscsi.route("/gateways", methods=["POST"])
@rbac.allow("iscsi.gateways.create")
def create_gateway(subject):
    return controller.create_gateway(subject), 204


@iscsi.route("/gateways/<gateway_id>", methods=["DELETE"])
@rbac.allow("iscsi.gateways.delete")
def delete_gateway(subject, gateway_id):
    return controller.delete_gateway(subject, gateway_id), 204


@iscsi.route("/disks", methods=["POST"])
@rbac.allow("iscsi.disks.create")
def create_disk(subject):
    return controller.create_disk(subject), 201


@iscsi.route("/disks", methods=["GET"])
@rbac.allow("iscsi.disks.list")
def list_disks(subject):
    return controller.get_disks(subject), 200


@iscsi.route("/disks/<disk_id>", methods=["DELETE"])
@rbac.allow("iscsi.disks.delete")
def delete_disk(subject, disk_id):
    return controller.delete_disk(subject, disk_id), 204


@iscsi.route("/disks/<disk_id>", methods=["PUT"])
@rbac.allow("iscsi.disks.update")
def update_disk(subject, disk_id):
    return controller.update_disk(subject, disk_id), 200


@iscsi.route("/clients", methods=["POST"])
@rbac.allow("iscsi.clients.create")
def create_iscsi_client(subject):
    return controller.create_client(subject), 201


@iscsi.route("/clients", methods=["GET"])
@rbac.allow("iscsi.clients.list")
def get_iscsi_clients(subject):
    return controller.get_clients(subject), 200


@iscsi.route("/clients/<client_id>", methods=["DELETE"])
@rbac.allow("iscsi.clients.delete")
def delete_client(subject, client_id):
    return controller.delete_client(subject, client_id), 204


@iscsi.route("/clients/<client_id>", methods=["PUT"])
@rbac.allow("iscsi.clients.update")
def update_client(subject, client_id):
    return controller.update_client(subject, client_id), 200


@iscsi.route("/clients/<client_id>/disks", methods=["POST"])
@rbac.allow("iscsi.disks.assign")
def disks_to_client(subject, client_id):
    return controller.disks_to_client(subject, client_id), 201


@iscsi.route("/clients/<client_id>/disks/<disk_id>", methods=["DELETE"])
@rbac.allow("iscsi.disks.unassign")
def unassign_client_disk(subject, client_id, disk_id):
    return controller.unassign_client_disk(subject, client_id, disk_id), 204


@iscsi.route("/clients/<client_id>/disks", methods=["GET"])
@rbac.allow("iscsi.disks.list")
def get_client_disks(subject, client_id):
    return controller.get_client_disks(subject, client_id), 200


@iscsi.route("/snapshots", methods=["GET"])
@rbac.allow("iscsi.snapshots.list")
def list_snapshots(subject):
    return controller.get_snapshots(subject), 200


@iscsi.route("/snapshots", methods=["POST"])
@rbac.allow("iscsi.snapshots.create")
def create_snapshot(subject):
    return controller.create_snapshot(subject), 201


@iscsi.route("/snapshots/<snapshot_id>", methods=["GET"])
@rbac.allow("iscsi.snapshots.get")
def get_snapshot(subject, snapshot_id):
    return controller.get_snapshot(subject, snapshot_id), 200


@iscsi.route("/snapshots/<snapshot_id>", methods=["PUT"])
@rbac.allow("iscsi.snapshots.update")
def update_snapshot(subject, snapshot_id):
    return controller.update_snapshot(subject, snapshot_id), 200


@iscsi.route("/snapshots/<snapshot_id>", methods=["DELETE"])
@rbac.allow("iscsi.snapshots.delete")
def delete_snapshot(subject, snapshot_id):
    return controller.delete_snapshot(subject, snapshot_id), 204


@iscsi.route("snapshots/<snapshot_id>/rollback", methods=["POST"])
@rbac.allow("iscsi.snapshots.rollback")
def rollback_snapshot(subject, snapshot_id):
    return controller.rollback_snapshot(subject, snapshot_id)
