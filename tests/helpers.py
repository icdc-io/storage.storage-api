def ensure_list(obj):
    """Ensures object is a list (wraps single objects)."""
    return obj if isinstance(obj, list) else [obj]
