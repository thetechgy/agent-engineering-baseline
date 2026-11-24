def require_runtime():
    """The released evaluator and Harbor pair for no-inference startup qualification."""
    pair = (importlib.metadata.version("skillevaluator"), importlib.metadata.version("harbor"))
    if pair != ("1.0.1", "0.25.0") or tuple(sys.version_info[:3]) != (3, 14, 10):
        raise RuntimeError("Unqualified gh backend owning runtime")
