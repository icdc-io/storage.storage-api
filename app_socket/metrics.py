import requests
from prometheus_client.parser import text_string_to_metric_families

from app_socket.config import CEPH_PROMETHEUS_HOST, log
from app_socket.utils import consolidate_metrics, get_metric_name

# Prometheus is polled from a background task, so a hung request would stall
# every subscriber. Never wait on it indefinitely.
REQUEST_TIMEOUT = 10


# Function to collect stats for every known image
def collect_all_stats():
    """Fetch and parse all ceph_librbd_ metrics from Prometheus.

    Kept separate from filtering so that a single poll can serve every
    subscriber instead of hitting Prometheus once per client.
    """
    log.debug(f"Collecting disk stats from Prometheus: {CEPH_PROMETHEUS_HOST}")
    return _collect_stats(f"http://{CEPH_PROMETHEUS_HOST}/metrics") or {}


# Function to keep only the images the client asked for
def filter_disk_stats(stats, query):
    return {name: stats[name] for name in query if name in stats}


# Function to send disk stats to the client
def send_disk_stats(query):
    return filter_disk_stats(collect_all_stats(), query)


# Helper function to collect stats from Prometheus
def _collect_stats(url):
    try:
        metrics = requests.get(url, timeout=REQUEST_TIMEOUT)

        # Check if the response status code is 200 (OK)
        if metrics.status_code != 200:
            log.error(f"Failed to retrieve metrics: HTTP {metrics.status_code}")
            return None

        # Check if the content type is 'text/plain', which is expected for Prometheus metrics
        if "text/plain" not in metrics.headers.get("Content-Type", ""):
            log.error("Unexpected content type, not Prometheus metrics.")
            return None

        log.debug(
            f"Raw Prometheus metrics: {metrics.text[:500]}..."
        )  # Log first 500 chars
        output = []

        # Parsing the metrics response
        for family in text_string_to_metric_families(metrics.text):
            if not family.samples:
                log.warning(f"No samples in metric family: {family.name}")
                continue

            if not family.name.startswith("ceph_librbd_"):
                continue

            metric = get_metric_name(family.name)
            if not metric:
                continue

            for sample in family.samples:
                labels = sample.labels
                if "ceph_daemon" in labels:
                    try:
                        image_name = labels["ceph_daemon"].split(":")[1]
                        output.append({image_name: {metric: sample.value}})
                    except IndexError:
                        log.warning(
                            f"Error splitting 'ceph_daemon' label: {labels['ceph_daemon']}"
                        )
                else:
                    log.warning(f"Missing 'ceph_daemon' label in sample: {sample}")

        res = consolidate_metrics(output)
        log.debug(f"Prepared metrics: {res}")
        return res
    except (
        requests.exceptions.ConnectionError,
        requests.exceptions.MissingSchema,
    ) as e:
        log.error(f"Prometheus host {CEPH_PROMETHEUS_HOST} is not responding: {e}")
        return None
    except Exception as e:
        log.error(f"Error processing Prometheus metrics: {e}")
        return None
