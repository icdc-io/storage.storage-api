import logging

import app.consts as consts

# Constants
CEPH_PROMETHEUS_HOST = consts.CEPH_PROMETHEUS_HOST

# engine.io path the server listens on. It must match both the nginx location that
# proxies to this service and the `path` option of the socket.io client.
WS_PATH = consts.get("WS_PATH", "/ws/disk_stats")

# How often (in seconds) subscribed clients are pushed fresh disk stats.
WS_STATS_INTERVAL = int(consts.get("WS_STATS_INTERVAL", 10))

# Setup logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
