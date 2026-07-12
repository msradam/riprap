"""Burr layer — first-class state machine on top of the pebble registry.

The runtime is composed of (conceptual graph shape — see riprap/core/burr/app.py
for the literal action names and wiring):

  intake       (planner + geocode; sets query, intent, lat, lon)
       ↓
  cornerstone  (MapActions: parallel fan-out over Cornerstone pebbles)
  touchstone   (MapActions: ditto for Touchstone)
  lodestone    (MapActions: ditto for Lodestone)
  keystone     (MapActions: ditto for Keystone)
       ↓
  capstone     (policy_corpus + reconcile + Mellea iterate)

Each Stone's pebble actions are generated at call time from the
manifest registry — there is no per-pebble @action boilerplate.
Adding a pebble in YAML automatically extends the Stone's fan-out.
"""
from riprap.core.burr.pebble import pebble_action, trace_rec_for
from riprap.core.burr.stones import (
    CornerstoneAction,
    KeystoneAction,
    LodestoneAction,
    TouchstoneAction,
)

__all__ = [
    "pebble_action",
    "trace_rec_for",
    "CornerstoneAction",
    "TouchstoneAction",
    "LodestoneAction",
    "KeystoneAction",
]
