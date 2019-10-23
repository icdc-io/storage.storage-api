# Helper to extract metric name based on family name
_METRICS_MAP = {
    "_rd": "read_iops",
    "_rd_bytes": "read_throughput_mb",
    "_wr": "write_iops",
    "_wr_bytes": "write_throughput_mb",
}


def get_metric_name(family_name):
    for suffix, metric in _METRICS_MAP.items():
        if family_name.endswith(suffix):
            return metric
    return None


# Helper to consolidate metrics
def consolidate_metrics(output):
    res = {}
    for item in output:
        image_name = list(item.keys())[0]
        if image_name not in res:
            res[image_name] = []
        res[image_name].append(item[image_name])

    for key in res:
        array = res[key]
        flattened = {}
        for item in array:
            flattened.update(item)
        res[key] = flattened
    return res
