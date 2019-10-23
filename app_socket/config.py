import logging

import app.consts as consts

# Constants
CEPH_PROMETHEUS_HOST = consts.CEPH_PROMETHEUS_HOST

# Setup logging
log = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
