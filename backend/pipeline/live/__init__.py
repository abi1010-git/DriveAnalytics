"""Live traffic-incident feeds. Each adapter module follows pipeline/live/base.py."""
from . import austin, chp, nj511, seattle, sf, wsdot

ADAPTERS = {module.SOURCE: module for module in (austin, chp, nj511, seattle, sf, wsdot)}
