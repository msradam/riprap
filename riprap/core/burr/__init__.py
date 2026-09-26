"""Burr layer: the briefing state machine on top of the pebble registry.

  intake     plan (LLM or regex) -> geocode (point) or resolve_area (NTA)
  routing    select_deployment by bounding box
  stones     one parallel fan-out over every Cornerstone, Touchstone,
             Keystone and Lodestone pebble for the intent
  capstone   policy_corpus, then reconcile (verified LLM claims or the
             no-LLM evidence briefing)

See riprap/core/burr/app.py for the wiring. Pebble actions are generated
from the manifest registry; adding a YAML manifest extends the fan-out.
"""
from riprap.core.burr.pebble import pebble_action, trace_rec_for
from riprap.core.burr.stones import StonesAction

__all__ = ["pebble_action", "trace_rec_for", "StonesAction"]
