<!---
# Create by: Daniil Satsura
# Origin: https://support.icdc.io/projects/ceph/wiki/Storage_classes
-->

# Storage classes

|Storage (device) Class|Crush Rule|
|---|---|
|nvme|replicated_nvme|
|ssd|replicated_ssd|
|hdd|replicated_hdd|
|hdd-cold|replicated_hdd-cold|

## Pools

|Pool|Pool App|Disk names|Crush Rule|Purpose|
|---|---|---|---|---|
|rbd|RBD|gateway.conf|any fasted|Store gateway.conf for all system iSCSI gateways|
|ovirt-nvme|RBD|data-nvme-1, data-nvme-2, engine-nvme-1|replicated_nvme|oVirt datastores, RBD disk with same prefix goes to single datastore `data-nvme`|
|ovirt-ssd|RBD|data-ssd-1, data-ssd-2|replicated_ssd|oVirt datastores|
|ovirt-hdd|RBD|backup-hdd-1, backup-hdd-2|replicated_hdd|oVirt datastores|
|openshift-nvme|RBD|csi-vol-*, kubernetes-dynamic-pvc-*|replicated_nvme|Openshift storage pool|
|iscsi-nvme|RBD||replicated_nvme|Storage iSCSI service account's disks|
|iscsi-ssd|RBD||replicated_ssd|Storage iSCSI service account's disks|
|iscsi-hdd|RBD||replicated_hdd|Storage iSCSI service account's disks|
|iscsi-hdd-cold|RBD||replicated_hdd-cold|Storage iSCSI service account's disks|
|mbs-nvme|RBD|volume-UUID|replicated_nvme|oVirt managed block storage Cinderlib|
|mbs-hdd|RBD|volume-UUID|replicated_hdd|oVirt managed block storage Cinderlib|
|default.rgw.nvme.*|S3||replicated_nvme|Storage S3 service account's buckets for default zone/zonegroup|
|default.rgw.ssd.*|S3||replicated_ssd|Storage S3 service account's buckets for default zone/zonegroup|
|default.rgw.hdd.*|S3||replicated_hdd|Storage S3 service account's buckets for default zone/zonegroup|
|default.rgw.hdd-cold.*|S3||replicated_hdd-cold|Storage S3 service account's buckets for default zone/zonegroup|
|cephfs.openshift.nvme.*|CephFS||replicated_nvme|CephFS for Openshift usage|
|cephfs.nextcloud.hdd.*|CephFS||replicated_hdd|CephFS for service disk (nextcloud) usage|

## iSCSI

Target IQNs:

```
iqn.2020-01.io.icdc.LOC:POOL_NAME

iqn.2020-01.io.scdc.LOC:POOL_NAME
```

Config for all targets and gateways is stored in the same `rbd/gateway.conf` to enable management from Ceph Dashboard.

> Note: Ceph Dashboard is limited to single config which it can manage for now.

Cases with multiple StorageDomains:

|Case|StorageDomain|Target|Gateways|Disks|Purpose|
|---|---|---|---|---|---|
|1|data-nvme|iqn.2020-01.io.scdc.xby:ovirt-nvme|ceph2 ceph3|data-nvme-1,data-nvme-2,data-nvme-3||
|2|data2-nvme|iqn.2020-01.io.scdc.xby:ovirt-nvme|ceph2 ceph3|data2-nvme-1,data2-nvme-2,data2-nvme-3|Multiple oVirt StorageDomains of same class on same gateways|
|3|data3-nvme|iqn.2020-01.io.scdc.xby:ovirt2-nvme|ceph1 ceph5|data3-nvme-1,data3-nvme-2,data3-nvme-3|Multiple oVirt StorageDomains of same class on different gateways|
|4|data-hdd|iqn.2020-01.io.scdc.xby:ovirt-hdd|ceph7 ceph8|data-hdd-1,data-hdd-2|Multiple oVirt StorageDomains of different class on different gateways|
|5|data2-hdd|iqn.2020-01.io.scdc.xby:ovirt2-hdd|ceph2 ceph3|data2-hdd-1,data2-hdd-2|Multiple oVirt StorageDomains of different class on same gateways|