def run_app(*args, **kwargs):
    from .main import run_app as _run_app

    return _run_app(*args, **kwargs)


__all__ = ["run_app"]
