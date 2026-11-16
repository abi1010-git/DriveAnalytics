"""Crash-record portals loaded through one configurable loader (see base.py)."""
import importlib
import pkgutil

from . import sources


def all_specs():
    """Every SPEC defined in pipeline/records/sources/*.py, keyed by source id."""
    specs = {}
    for info in pkgutil.iter_modules(sources.__path__):
        module = importlib.import_module(f"{sources.__name__}.{info.name}")
        spec = getattr(module, "SPEC", None)
        if spec is not None:
            specs[spec.source] = spec
    return dict(sorted(specs.items()))
