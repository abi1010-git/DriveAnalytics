"""Live traffic-incident feeds. Each adapter module follows pipeline/live/base.py."""
from . import austin

ADAPTERS = {module.SOURCE: module for module in (austin,)}
