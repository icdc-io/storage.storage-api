Integration tests live here when they require real external systems.

Current state:
- `tests/unit/` is the fake/stub layer.
- `tests/api/` is the Flask + database layer.
- Ceph-backed iSCSI request tests now live under `tests/integration/iscsi/`.

Migration rule:
- New real-Ceph tests should go under `tests/integration/`.
- If a test uses fixtures like `disk_ceph`, `disk_ceph_factory`, `assigned_ceph_factory`,
  `client_ceph_assigned`, or `ceph_unassign_client`, it belongs here.
