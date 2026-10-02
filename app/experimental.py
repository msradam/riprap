"""Riprap's three experimental models, and the one rule for quoting them.

The surge and water models are the owner's fine-tunes, published on Hugging
Face and reproduced at github.com/msradam/riprap-models; the land-cover model
is trained in this repository (scripts/train_cover.py) and its weights are
not published. None has been shown to
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
# The land-cover model's weights are local (app/eo/cover.py); its saved maps carry this hash.
COVER_SHA256 = "15dc40f93277f456537d2705e538c7f333e561b40784b2aabfda1eec67c50116"


@dataclass(frozen=True)
class Model:
    name: str  # in words, for a sentence
    repo: str | None  # the owner's Hugging Face repository; None when the weights are not published
    revision: str  # the pin: a commit of `repo`, or the SHA-256 of the local weights when `repo` is None
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
        name="NYC land-cover model",
        repo=None,  # trained by scripts/train_cover.py; the weights are not published
        revision=COVER_SHA256,
        extra="eo",
        limits="it estimates the share of each 10 m satellite pixel that is canopy, grass, paving, roof, water or "
               "bare ground, learned from the city's 2017 six-inch map, so detail finer than about 30 m is blurred "
               "and a tree over a street counts as canopy",
        evaluation="against the city's own 2021 six-inch map, on squares it never trained on, it read a typical "
                   "district's paved share {district_paved_vs_city_map} the map's (at most "
                   "{district_paved_gap_points_max} points off in the {n_districts} districts with enough test "
                   "ground) and its mean error per land-cover group was "
                   "{model_test_mae_points} points at best, more than the {city_map_2017_as_2021_mae_points} points of the "
                   "city's 2017 map read as if it were 2021, so the 2017 map is the more accurate source for its "
                   "year; two images of one summer differ by under {noise_points} points in a district's paved share "
                   "19 times in 20, but between {between_years_worst} the shares of {between_years_beyond_noise} of "
                   "{between_years_districts} districts differ by more, so its maps of different years are not "
                   "compared",
        official="NYC's own land cover maps (2017 and 2021, 6 inch) and building footprints for a survey",
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
