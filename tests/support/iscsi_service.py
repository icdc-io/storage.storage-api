from unittest.mock import Mock

from app.models.iscsi_target import IscsiTargets


def build_iscsi_service_mock():
    service = Mock()
    service.create_disk.return_value = {"code": 200, "data": {}}
    service.new_disk_from_snapshot.return_value = {"code": 200, "data": {}}
    service.update_disk.return_value = {"code": 200, "data": {}}
    service.assign_disk.return_value = {"code": 201, "data": {}}
    service.disconnect_disk.return_value = {"code": 204, "data": {}}
    service.update_client.return_value = {"code": 200, "data": {}}
    service.create_snapshot.return_value = {"code": 201, "data": {"size": 1}}
    service.delete_disk.return_value = {"code": 204, "data": {}}
    service.delete_client.return_value = {"code": 204, "data": {}}
    return service


def install_iscsi_service_mock(monkeypatch):
    service = build_iscsi_service_mock()
    monkeypatch.setattr(
        IscsiTargets,
        "iscsi_service",
        Mock(return_value=service),
    )
    return service
