"""Riprap's three experimental models, and the one rule for quoting them.

The models are the owner's fine-tunes, published on Hugging Face and
reproduced at github.com/msradam/riprap-models. None has been shown to
beat an official product, so nothing they produce is ever a measurement:

  * every sentence from a model goes through `hedge`, which opens it with
    "Experimental" (or "Experimental forecast" for the future), states the
    model's limits and its tested accuracy, and names the official source
    to rely on;
  * the accuracy sentence is filled from a result file under
    `data/experimental/`, written by the model's own backtest script, so
    the hedge changes when the evidence does and never by hand;
  * for a question about the past or the present a model never sets the
    lead and never stands behind a "Yes" (riprap/core/burr/synthesis.py).

A model whose optional extra is not installed, or whose saved output is
missing, says so in one sentence (`not_installed`).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "experimental"


@dataclass(frozen=True)
class Model:
    name: str  # in words, for a sentence
    repo: str  # the owner's Hugging Face repository
    revision: str  # pinned commit: weights never change under a running app
    extra: str  # the optional dependency group that runs it
    limits: str  # what it cannot see, as a clause
    evaluation: str  # a clause with {fields} filled from data/experimental/<key>.json
    official: str  # what a person should rely on instead


MODELS = {
    "surge": Model(
        name="Granite TTM r2 Battery Surge",
        repo="msradam/Granite-TTM-r2-Battery-Surge",
        revision="181b892bf4c4693018a834d359427c279b315213",
        extra="ml",
        limits="it reads only the last 1,024 hours of the Battery gauge, with no wind or pressure input, so it "
               "cannot see a storm that has not yet reached the gauge",
        evaluation="on {n_windows} past 96-hour windows ({first} to {last}) its mean error was {mae_cm} cm, against "
                   "{baseline_mae_cm} cm for assuming the last day's mean continues, and it foresaw {n_flood_foreseen} "
                   "of the {n_flood_windows} windows in which the water reached the minor flood stage",
        official="the National Weather Service (weather.gov/okx) and Notify NYC; NOAA's ETSS and the Stevens Flood "
                 "Advisory System model surge from the weather",
    ),
    "water": Model(
        name="Prithvi-EO 2.0 NYC Pluvial",
        repo="msradam/Prithvi-EO-2.0-NYC-Pluvial",
        revision="25ce564199d8cfa8fefd5ac0e80e2d911b65ea60",
        extra="eo",
        limits="a satellite passes every few days and sees 10 to 20 m pixels, so street and basement flooding that "
               "drains within hours is invisible to it, and its training labels were the base model's own output "
               "for Hurricane Ida, not surveyed flooding",
        evaluation="of {n_marks} high-water marks USGS surveyed after Ida, it showed new water within 500 m of "
                   "{n_marks_with_water} ({marks_pct}%), {against_chance} ({chance_pct}% of the land it saw lies "
                   "that close to its new water)",
        official="the surveyed and measured record (USGS high-water marks, FloodNet sensors) and NYC DEP's "
                 "stormwater flood maps",
    ),
    "landcover": Model(
        name="TerraMind NYC land-cover adapter",
        repo="msradam/TerraMind-NYC-Adapters",
        revision="984341631d10db4fb699f76cd5d5bc7d8b3690b3",
        extra="eo",
        limits="it labels 10 m satellite pixels and is a proxy, not a survey: a pixel that mixes street, roof, tree "
               "and shadow gets one label, and it calls much green ground paved",
        evaluation="for {eval_year} it agreed with ESA WorldCover (its own label source) on {group_agreement_pct}% of "
                   "the city's land as paved, green or water and found {green_found_pct}% of WorldCover's green land, "
                   "its paved share for a typical district was {district_built_vs_worldcover} WorldCover's, and two "
                   "images of one year differ by under {noise_points} points in a district's paved share 19 times in "
                   "20 ({noise_points_small} in a neighbourhood's)",
        official="NYC's own land cover map (2017, 6 inch) and building footprints for a survey",
    ),
}


def evaluation(key: str) -> dict | None:
    """The model's latest backtest result, or None when none is saved."""
    path = EVAL_DIR / f"{key}.json"
    return _read(path, path.stat().st_mtime) if path.exists() else None


@lru_cache(maxsize=8)
def _read(path: Path, mtime: float) -> dict:  # a result file written while the app runs is read again
    return json.loads(path.read_text())


def hedge(key: str, statement: str, *, forecast: bool = False) -> str:
    """The only way a model's output becomes a sentence: label, statement,
    limits and tested accuracy in one sentence, then the official source.
    `forecast` marks a statement about the future."""
    m = MODELS[key]
    result = evaluation(key)
    try:
        tested = m.evaluation.format(**result) if result else "it has no saved evaluation"
    except KeyError:  # a result file from an older backtest, without a field the sentence quotes
        tested = "its saved evaluation is out of date"
    label = "Experimental forecast" if forecast else "Experimental"
    return (f"{label}: {statement.rstrip('. ')}. Limits: {m.limits}; {tested}. "
            f"Rely on {m.official}.")


def not_installed(key: str, what: str) -> str:
    """The sentence shown in place of a model output the server cannot make."""
    m = MODELS[key]
    return (f"Experimental: {what} is not available on this server; it needs the optional "
            f"{m.extra} extra (uv sync --extra {m.extra}).")
