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


# Helper to normalize the `disks` payload sent by clients
def parse_disks(value):
    """Normalize a `disks` payload into a list of image names.

    Clients are inconsistent here: the value may arrive as a comma separated
    string, as a list of names, or as a list of comma separated strings.
    """
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]

    disks = []
    for item in value:
        for name in str(item).split(","):
            name = name.strip()
            if name and name not in disks:
                disks.append(name)
    return disks


# Helper to read the `disks` parameter out of the connection query string
def parse_disks_from_args(args):
    """socket.io-client serializes an array query parameter as `disks[]=a&disks[]=b`,
    so both spellings are accepted."""
    return parse_disks(args.getlist("disks") + args.getlist("disks[]"))
