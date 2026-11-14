def require_runtime():
    """The separately qualified 0.9.0 owning pair only."""
    pair = (importlib.metadata.version("skillevaluator"), importlib.metadata.version("harbor"))
    if pair != ("0.9.0", "0.25.0") or tuple(sys.version_info[:3]) != (3, 14, 10):
        raise RuntimeError("Unqualified gh backend owning runtime")
