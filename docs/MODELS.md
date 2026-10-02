---
type: reference
---

# Models and inference energy

## What a briefing needs

No model. A briefing is built from the data, and a question is answered by
rules over its words (`riprap/core/burr/rule_answer.py`). Riprap ships no
weights.

Two kinds of model are optional.

**An LLM**, behind any OpenAI-compatible endpoint (`RIPRAP_LLM_BASE_URL`,
`RIPRAP_LLM_MODEL`); it was tested with Granite 4.1 8B
(`hf.co/ibm-granite/granite-4.1-8b-GGUF:Q4_K_M` over Ollama). The rules
answer first even then. The model is asked only when the rules do not
recognise a question or cannot read its place: it plans the query, chooses
a lead and up to four cited facts, and code checks that choice; the answer
text is the sources' own sentences ([`docs/GROUNDING.md`](GROUNDING.md)).
The gallery is built with no LLM.

**Three experimental models**, described below. They are the author's
fine-tunes: one forecasts surge at the Battery, one reads satellite scenes
after storms, one maps paved, green and tree-covered land.

`app/models_info.py` lists the models behind each result in its `models`
field, and `/api/models` says which this server can use.

An earlier probe had the LLM rewrite the evidence for ten gallery addresses
as claims (the mode now behind `RIPRAP_LLM_BARE=1`). `granite4:micro` kept
122 claims and dropped 0, and `llama3.1:8b` kept 191 and dropped 0
(`tests/probe_grounding_results*.json`).

## Experimental models

The gallery answers three questions with these models:
[the Battery surge](https://msradam.github.io/riprap/gallery/battery-surge/),
[surface water in BK18 after Ida](https://msradam.github.io/riprap/gallery/bk18-satellite/)
and [paved, green and tree-covered land in QN12](https://msradam.github.io/riprap/gallery/qn12-paved/).

Riprap is an app in development, and these three models are part of it.
None has been shown to beat an official product. So their output is never
shown as a measurement:

- Every sentence from a model is written by one function,
  `hedge` in [`app/experimental.py`](../app/experimental.py). It opens with
  "Experimental" (or "Experimental forecast" for the future), gives the value
  with its unit, time window and place, then the model's limits and its
  tested accuracy in one sentence, then the official source to rely on.
- The accuracy clause is filled from a result file under
  `data/experimental/`, written by the model's own test script. When a test
  is rerun the sentence changes with it. Nobody edits it by hand.
- For a question about the past or the present a model never sets the
  answer's yes or no, and its sentence comes after the record. A question
  about what a model showed ("did satellite imagery show flooding here
  after Ida") gets the surveyed record first and no yes or no at all, so
  the record's "Yes." cannot be read as the model's.
- When the question asks only for what a model produces (land cover, what
  the imagery showed in a district) and no official source in the briefing
  answers the same thing, the lead is "From an experimental model, not a
  measurement:". When an official source does answer, it comes first.
- A language model, when one is configured, cannot rest a yes or no on an
  experimental source: code checks the lead against the measured facts only.
- "Will it flood here" is not answered yes or no by anything. The lead says
  no source or model predicts that, and what the Weather Service expects and
  the maps show follows.
- In a plain place briefing a model's sentence appears only when it shows
  something (a notable surge, new water after Ida). It is always in the
  evidence table, under "Experimental sources".
- On screen each sentence carries an "Experimental" badge; the print packet
  prints the same text; MCP items carry `maturity: "experimental"`.

| Model | Repository and pinned commit | Runs | Extra |
|---|---|---|---|
| Granite TTM r2 Battery Surge | [`msradam/Granite-TTM-r2-Battery-Surge`](https://huggingface.co/msradam/Granite-TTM-r2-Battery-Surge) at `181b892` | per request, on CPU (about 0.1 s) | `ml` |
| Prithvi-EO 2.0 NYC Pluvial | [`msradam/Prithvi-EO-2.0-NYC-Pluvial`](https://huggingface.co/msradam/Prithvi-EO-2.0-NYC-Pluvial) at `25ce564` | in a batch job; the app reads the saved rasters | `eo`, for the batch only |
| NYC land-cover model | not published; trained by `scripts/train_cover.py` on [`ibm-esa-geospatial/TerraMind-1.0-base`](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base) at `fb96c70`, weights pinned by SHA-256 `15dc40f` | in a batch job; the app reads the saved rasters | `eo`, for the batch only |

The author's weights are loaded from safetensors files at those commits,
or, for the land-cover model, from a local safetensors file whose SHA-256
must match. The TerraMind base is published only as a PyTorch checkpoint;
it is read with `weights_only=True`, which admits tensors and no code. The
surge and water models were trained on AMD Developer Cloud and are
reproduced independently at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models);
the land-cover model was trained on an Apple M5 in this repository.

A default install has none of this: `uv sync` installs no torch, the surge
source then says "the Battery surge forecast model is not available on this
server; it needs the optional ml extra", and the satellite layers are read
from `data/eo/` with the core dependencies.

```bash
uv sync --extra ml                                    # the surge forecast
uv sync --extra eo                                    # to rerun the batch jobs
uv run python scripts/backtest_surge.py               # writes data/experimental/surge.json
uv run python scripts/run_eo_batch.py --heavy-rain-since 2017 --min-inches 1.5
uv run python scripts/run_landcover_batch.py --years 2018 2021 2024 2026
```

### Granite TTM r2 Battery Surge

It reads the last 1,024 hourly values of the surge residual at NOAA station
8518750 (The Battery): observed water level minus NOAA's predicted tide. It
writes the next 96. Riprap adds NOAA's tide predictions to get a total water
level and holds it against the flood stages the Weather Service publishes
for that gauge (minor 7.0 ft above MLLW). The model was trained and tested
on unbroken hours, so when the gauge's last 1,024 hours have a gap, or its
last reading is more than six hours old, the source declines and says why.

| Question | Answered | How |
|---|---|---|
| Will the water at the Battery run above the predicted tide in the next four days, by how much and when | Yes | The highest forecast residual and its hour |
| Could high tide tonight reach minor flood level in lower Manhattan | Yes | The highest forecast total against the gauge's stages, after the Weather Service's own forecast for the same gauge |
| Which subway entrances or buildings near the shore sit below the forecast peak | No | See below |
| Anything at Kings Point, Sandy Hook or another gauge | No | Trained on the Battery only |
| A surge from a storm that has not reached the gauge | No | It has no wind or pressure input |

Backtest, `scripts/backtest_surge.py`, run 2026-10-01: 635 windows, one a
day from 2025-01-01 to 2026-09-27, all after the training data ends
(2024-12-31). Truth is the gauge.

| Mean absolute error over 96 hours | Model | Last day's mean held | Last value held | Predicted tide alone |
|---|---|---|---|---|
| All 635 windows | 0.115 m | 0.133 m | 0.133 m | 0.167 m |
| 109 windows with a residual of 0.5 m or more | 0.209 m | 0.241 m | 0.246 m | 0.281 m |
| Error in the peak, all windows | 0.157 m | 0.240 m | 0.237 m | 0.360 m |

So it beats the plain baselines by about 14% on average. It does not see
floods coming: of the 23 windows in which the water reached the minor flood
stage, its forecast reached it in 1, with 1 false alarm. Holding the last
day's mean reached it in 6, with 5 false alarms. Both numbers are in every
surge sentence.

An earlier check on 104 windows from one calm stretch (May to September
2026) found the model level with the last day's mean (0.083 m against
0.085 m), and the forecast was removed on that evidence. The longer record
above, with two winters in it, is the fairer test.

Newer open forecasters, zero-shot, on the same 635 windows
(`scripts/backtest_surge_candidates.py`, run 2026-10-02,
`data/experimental/surge_candidates.json`). Each reads the same 1,024
hours; a model that gives quantiles is scored on its median.

| Model | Mean error, all | Mean error, 109 storm windows | Error in the peak | Minor flood windows foreseen (of 23), false alarms | Difference from the current model, 95% interval |
|---|---|---|---|---|---|
| Current (TTM r2, fine-tuned) | 0.115 m | 0.209 m | 0.157 m | 1, 1 | |
| Granite TTM r3 | 0.115 m | 0.213 m | 0.189 m | 2, 0 | -0.5 to +0.5 cm |
| Granite FlowState r1.1 | 0.113 m | 0.212 m | 0.177 m | 2, 2 | -0.6 to +0.3 cm |
| Granite PatchTST-FM r2 | 0.109 m | 0.209 m | 0.174 m | 3, 2 | -1.0 to -0.3 cm |
| Chronos-2 | 0.110 m | 0.210 m | 0.178 m | 3, 2 | -0.9 to -0.1 cm |
| Chronos-2 fine-tuned on the Battery (2015 to mid 2024) | 0.106 m | 0.205 m | 0.158 m | 2, 0 | -1.2 to -0.5 cm |
| Last day's mean held | 0.133 m | 0.241 m | 0.240 m | 6, 5 | +1.1 to +2.6 cm |

The interval comes from resampling the windows in runs of 14 days, since
windows a day apart share three of their four days. PatchTST-FM r2 and
Chronos-2 beat the current model's mean error by about half a centimetre,
which is real but small. Every one of them misses the peak by more, and the
peak is what a surge sentence quotes. Their 90th percentiles reach the
minor flood stage in 7 to 10 of the 23 windows, at the cost of 32 to 60
false alarms in 612 windows that stayed below it. None of them, zero-shot,
replaces the current model.

Because two came close, one was fine-tuned (`scripts/finetune_chronos2_surge.py`):
a LoRA adapter on Chronos-2, trained on the Battery residual before
2024-07-01, with the checkpoint chosen on the second half of 2024 (step 200
of 700; the loss rose after). It beats the current model on mean error by
0.9 cm, with the interval clear of zero, is level on the peak, and foresees
2 of the 23 flood windows with no false alarm. The 23 windows come from five
storms, so 2 against 1 is about one storm. Two cautions: the backtest reads
the gauge's value at the top of each hour, while the current model's card
says it trained on hourly means, which may favour a model trained the way it
is tested; and what the zero-shot models saw in pretraining is not known
here. So the fine-tune is better on the average by a small margin and level
on the peak, and it still misses 21 of the 23 floods; the sentence's real
weakness stays. It is not in the app: the surge forecast
runs per request, so the server needs the weights, and these are on the
owner's machine only (`outputs/surge_models/chronos2_battery/`, 478 MB of
safetensors). Switching needs the owner to publish them, and adds the
`chronos-forecasting` package to the `ml` extra.

Not built: the list of assets below the forecast peak. On the days that
matter the model's peak is too low (1 of 23), so the list would be empty
when a flood came, and a 30 m elevation model cannot place a subway entrance
within the half metre that separates an ordinary high tide from a minor
flood.

For the owner: the model card says Hurricane Ida was surge-driven and that
it "falls within the test window". Ida in New York was a rainfall flood, and
with a 70/15/15 split of 2015 to 2024 the test window starts in mid 2023, so
Ida (September 2021) is in the training data. The card is in another
repository and is not edited from here.

### Prithvi-EO 2.0 NYC Pluvial

It labels each 10 m pixel of a Sentinel-2 scene as water or not.
`scripts/run_eo_batch.py` runs it on the clearest scene from the two days
after a heavy rain and on a scene from the month before, and keeps the land
pixels that are water after and were not before, where both scenes had a
clear view. It was run for every day since 2017 with 1.5 inches of rain or
more at Central Park: 15 of 50 such events had a usable pair of scenes.

| Question | Answered | How |
|---|---|---|
| Did satellite imagery show standing water near this place after Hurricane Ida | Yes, as what the model showed | New water within 500 m, the scenes' dates, the share observed |
| How much new surface water appeared in this district after Ida | Yes, as what the model showed | The same, over the district |
| After which other storms did it show new water here | Yes | The saved events with a clear view of the place |
| Is this area prone to water that lingers after heavy rain | No | Tested and failed, see below. The question is answered from the city's stormwater flood map |
| Did the street or a basement flood | No | That water drains within hours; a satellite passes days apart and sees 10 to 20 m pixels |

Test against surveyed flooding, `scripts/run_eo_batch.py --evaluate-only`,
run 2026-10-01. USGS surveyed 153 high-water marks after Ida in places the
scenes saw clearly. The model shows new water within 500 m of 17 of them,
11%. Of all the land it saw, 14% lies within 500 m of its new water. So a
surveyed flood mark is no more likely to be near the model's water than a
random spot. Every satellite sentence says so.

Test of the lingering-water idea: land that showed new water after two or
more storms (1.73 km², among land seen in at least three) should be
flood-prone if the idea held. The city's stormwater flood map (DEP moderate
scenario, current sea level) covers 1.4% of the land the model saw and 0.7%
of that recurrent land. The recurrent land is concentrated in Forest Park,
Silver Lake and Grymes Hill, and Todt Hill: wooded slopes, where shadow
moves between two scenes. So no "prone to lingering water" answer is built.

The training labels were the base model's own output for Ida (166
polygons, and 332 copies of them pasted onto other scenes), so the model
card's flood score of 0.60 measures agreement with itself. The owner's
reproduction scored 0.08 to 0.12 on real scenes.

#### The official flood model, same test

IBM and ESA publish `TerraMind-base-Flood`, fine-tuned on ImpactMesh-Flood
(Copernicus EMS flood maps with Sentinel-1 radar, Sentinel-2 and the
Copernicus DEM over four dates: a month before, just before, the event and
after). `scripts/run_flood_ida.py` ran it over the city for Ida (run
2026-10-02): Sentinel-2 on 13 and 25 August, 2 September (the Prithvi
layer's post scene) and 7 September; radar on 26 July, 19 August,
12 September and 24 September. Planetary Computer has no radar pass that
covers the city between 19 August and 12 September, so the radar's event
image is 11 days after the rain.

| Measure | TerraMind-base-Flood | Prithvi NYC Pluvial |
|---|---|---|
| Land the model marks as flooded, of the land both saw | 0.06 km² | 3.79 km² of new water |
| Surveyed Ida marks with flood within 500 m | 4 of 153 (3%) | 17 of 153 (11%) |
| Share of the land within 500 m of the model's flood (chance) | 1.2% | 14% |

The four marks are one place in Van Cortlandt Park in the Bronx: two survey
sites 214 m apart, on the golf course beside the Major Deegan and at Van
Cortlandt Pool, on ground that was dry before the storm. Counted as independent, four hits against a 1.2% chance rate
would come up one time in ten by luck (binomial, `p = 0.10`). At a lower
threshold that nobody would have chosen in advance (a flood probability
of 0.1) it reaches 13 marks at two places. So it has no citywide skill on
Ida either.

The model works on its own kind of data. On 300 of ImpactMesh's validation
patches, with the same model loading and normalisation, it finds the flood
water Copernicus mapped with an IoU of 0.615 and a recall of 0.907
(`data/experimental/flood_terramind_impactmesh_check.json`). Validation
patches can come from events seen in training, so this checks the setup,
not skill on a new place. The Ida inputs it does not exercise (the band
order, radar in dB, the dates in order, the elevation repeated) were checked
by hand against the dataset's own files. Over the city's land the radar's
medians are about -5.6 dB (VV) and -12.8 dB (VH) on every date, brighter than
the dataset's means of -10.0 and -16.0 as built-up ground is, and far from
what linear values would give. Dense city is also unlike most of the floods
the model was trained on. Nothing in this
test separates the model from the timing: the optical event image is a day
after the rain and the radar's eleven days. A satellite that passes a day or
more after a flood that drained within hours cannot see it, and tuning a
model does not move the pass.

Recommendation for the owner: retire the satellite water layer rather than
tune it. Two models of different make, one of them official and working as
designed on its own data, both miss Ida's flooding. The result file is
`data/experimental/flood_terramind_ida.json`; the weights are listed under
provenance below.

### NYC land-cover model

Since 2026-10-02 the land-cover layer comes from a model trained here on the
city's own map. It estimates, for each 10 m Sentinel-2 pixel, the share in
eight classes: tree canopy, grass and shrub, bare soil, water, building, road,
other paved and railroad. Riprap reports three groups (paved or built over,
green, water) and, inside green, the tree canopy share, which matters for
urban heat.

It is TerraMind 1.0 base (IBM and ESA, the same pinned checkpoint as before)
with a UNet decoder, plus a small per-pixel network on the twelve bands whose
output is added to the decoder's. A ViT token is 16 pixels (160 m) across and
its decoder never sees one pixel's spectrum; the per-pixel branch supplies
that. `scripts/train_cover.py` trains it on two summer 2017 Sentinel-2 dates
against the city's 2017 six-inch land cover map (NYC Open Data), counted into
10 m cells, with a soft-label cross-entropy. The encoder learns at a tenth of
the decoder's rate, and the weights that score best on validation squares are
kept. Training took 49 minutes on an Apple M5. The weights (412 MB of
safetensors) are not published; `app/experimental.py` pins them by SHA-256
(`15dc40f`), and the batch job refuses a file with another hash.

**The test.** The city is cut into 2 km squares; one in five is a test square
the model never saw in training. Each model is scored on 2021 Sentinel-2
images of those squares against the city's 2021 six-inch map (The Nature
Conservancy and UVM, built from 2021 LiDAR and imagery), so the key is a
different year, method and sensor from the training labels. That map is
CC BY-NC-SA: it is used on this machine as a key only, and nothing drawn
from it is in this repository except scores. Cells are 30 m (3 by 3 pixels),
because Sentinel-2 is located to about a pixel. Training chips can include
test-square imagery as context, never its labels. Two 2021 images were
scored, 16 June and 29 September (`scripts/eval_cover.py`,
`data/experimental/landcover_nyc_eval.json`).

The work ran in two rounds, and the test was read after the first. In the
first round every model kept its last weights and TerraMind trained at one
learning rate; TerraMind lost to the UNet (test error 6.2 and 5.3 points for
the UNet, 8.8 and 8.2 for TerraMind base, which overfit). The per-pixel
branch, the slower encoder rate and keeping the best weights on validation
came from that. In the second round, below, every model was retrained under
those rules and the model was chosen on the validation squares (0.086
against 0.089 for TerraMind small with the branch). That rule was set before
the chosen model's test scores were read, though the small model's had been,
and the two are level on the test. So the design was not blind to the test;
the final choice was made on validation.

| Model, 2021 test squares | Mean error per group (points), June / Sept | Canopy R² | Paved R² | A district's paved share against the map (median gap, points) | Two images of 2021, district paved share (19 in 20 under) |
|---|---|---|---|---|---|
| This model (TerraMind base with a per-pixel branch) | 5.3 / 4.8 | 0.77 / 0.83 | 0.90 / 0.90 | 1.9 / 2.2 | 2.0 |
| The same, second seed | 5.3 / 4.8 | 0.76 / 0.83 | 0.90 / 0.90 | 1.7 / 2.5 | 1.8 |
| TerraMind small with a per-pixel branch | 5.4 / 4.8 | 0.77 / 0.82 | 0.90 / 0.90 | 1.4 / 2.0 | 2.1 |
| TerraMind base alone | 6.8 / 6.3 | 0.62 / 0.72 | 0.81 / 0.80 | 4.2 / 4.5 | 3.8 |
| TerraMind small alone | 6.6 / 6.0 | 0.66 / 0.73 | 0.84 / 0.83 | 1.7 / 3.2 | 5.5 |
| TerraMind tiny alone | 7.0 / 6.6 | 0.65 / 0.70 | 0.83 / 0.81 | 1.3 / 3.3 | 5.7 |
| A UNet with no pretraining (two seeds) | 6.4 / 5.5 and 6.3 / 5.4 | 0.64 / 0.76 | 0.89 / 0.88 | 1.0 / 1.1 and 1.3 / 3.4 | 4.0 and 5.6 |
| A per-pixel network on the twelve bands | 6.5 / 6.3 | 0.73 / 0.72 | 0.86 / 0.84 | 2.2 / 3.4 | 7.0 |
| A probe on TESSERA embeddings (one per year; `geotessera` 0.10.2, registry v1, CC0) | 6.4 / 6.2 | 0.81 / 0.81 | 0.78 / 0.79 | 3.1 / 2.9 | n/a |
| The old `lulc_nyc` adapter | 11.6 / 11.4 | 0.0 / -0.1 | 0.19 / 0.22 | 18.1 / 16.2 | 3.8 |
| The 2017 map itself, read as 2021 | 3.0 / 2.9 | 0.93 / 0.92 | 0.92 / 0.92 | 1.6 / 1.5 | 0 |

So TerraMind earns its place only with the per-pixel branch: alone, every
size is worse than a UNet with no pretraining; with it, it beats every other
model on mean error and on paving, and on canopy every model but the
TESSERA probe, and it is the steadiest between two images of one year. (The
UNet's first-round weights, its last rather than its best on validation,
scored 6.2 and 5.3, a little better than the 6.4 and 5.5 above; either way
it trails.) The adapter's "trees and shrubs" class is counted as canopy
here, while the city map counts shrub as grass and shrub; that costs it on
canopy but does not touch its paved bias. The old adapter read a district's paved share 16 to 18
points high against the city's own map, more than twice the 7.7 points it
showed against WorldCover, and it had no skill on tree canopy. The 2017 map
read as 2021 is better than any model for 2021, which is expected (most
ground does not change in four years); the model's use is the years and
places no six-inch map covers.

**Change between years.** On the test squares, the model's change in a 30 m
cell's paved share from 2017 to 2021 correlates with the two maps' change at
r = 0.42 (canopy 0.45); the UNet's is 0.38 (0.29) and the old adapter's 0.16
(0.17). The maps' own change is partly method: they were made five years
apart with different imagery, and "other paved" falls 2.3 points citywide
between them. At 1,530 sites of DOB new-building permits issued 2016 to 2019
on test squares, the model's paved share rose 3.3 points against 0.4 at
7,650 sites with no new-building or demolition permit within 200 m; a site's
rise exceeds a control's 57% of the time (AUC 0.57). The maps themselves
manage 0.59 on the same sites, so a permit point is a weak marker of change
at 30 m, and the model sees about as much of it as the maps do.

**In the app.** `scripts/run_landcover_batch.py` maps each summer since 2018
with the clearest full-city dates, writes five percent bands at 30 m to
`data/eo/landcover_<year>.tif`, and scores the 2021 map against the city's
2021 map on the test squares. For 2021 it
reads a typical district's paved share 1.7 points above the city map's on
the test squares (median gap 1.8 points, largest 7.8); a 30 m cell's paved
share is off by 6.6 points on average (R² 0.90) and its canopy share by 8.4
(R² 0.77). Two images of one year differ by under 2.0 points in a district's
paved share 19 times in 20 (2.7 in a neighbourhood's).

Maps of different summers differ by much more. Every pair of years mapped
is compared the same way, district by district, on the 10 m maps in the
batch (the saved 30 m maps, rounded to whole percents, give slightly lower
counts with the same order):

| Years | Districts whose paved shares differ by more than 2.0 points |
|---|---|
| 2018 and 2021 | 11 of 59 |
| 2021 and 2026 | 11 of 59 |
| 2018 and 2026 | 25 of 59 |
| 2024 and 2026 | 30 of 59 |
| 2021 and 2024 | 35 of 59 |
| 2018 and 2024 | 49 of 59 |

The 2024 map, made from one September image, stands apart from the rest,
and even the closest pairs exceed what two images of one summer produce
(the threshold is their 95th percentile, so about 3 of 59 by design). That is the images, not the ground. So the app reports
the latest year only, and every land-cover sentence says that no change
between years is read from the maps and why
(`data/experimental/landcover.json`). The maps are saved at 30 m, the scale
the model is scored at, as five bands: canopy, grass and shrub, bare soil,
water, and paved or built over.

| Question | Answered | How |
|---|---|---|
| How much of this place is paved or built over, how much is green, how much is tree canopy | Yes | Mean shares of the latest year's map |
| How has it changed since a given year | No | Maps of different summers differ by more than the model's noise (above); the sentence says so |
| If this paving trend continues, is runoff likely to rise | No | No change is read, so no trend is |
| Has new construction appeared | No | DOB permits and building footprints are the record; at a permit site the model and the maps both separate weakly |

#### The adapter it replaced

The `lulc_nyc` adapter (`msradam/TerraMind-NYC-Adapters` at `9843416`) was
trained on ESA WorldCover, and three things differed from its card, each
checked on one box of Manhattan, Brooklyn and Queens against WorldCover 2021
(`data/experimental/landcover_checks.json`). Its classes are the training
script's (water, built-up, trees and shrubs, grass and crops, other; with
the script's order it agrees with WorldCover on 90.5% of pixels), not the
card's, and there is no building class. Its radar and elevation inputs
carry nothing: zeros give the same map. And its `buildings_nyc` sibling
flips 4.6% of pixels between two images of one year, so it cannot show new
construction.

The thinking-in-modalities adapter (`tim_nyc`) first generates TerraMind's
own land cover tokens with a second encoder and decoder (the sampler) and
then reads them beside the image. An earlier note said the generation
weights were in neither repository. They are in the pinned base checkpoint;
the first check built the model without them, so its sampler was random.
It left 310 of the sampler's 323 tensors random (13 are shared with the
encoder embeddings it did load). `scripts/check_tim.py` loads all 323
through TerraTorch's own filter, which raises if one is missing (a separate
check found each equal to the checkpoint), and reruns the same box and key.
On 2021-06-16, with Sentinel-2 on the app's scale (scenes before 2022
lifted by 1000, which is why `lulc_nyc` reads 90.2% here and 90.5% in the
unlifted run above), the corrected `tim_nyc` agrees with WorldCover on 89.8%
of pixels with each of three generation seeds (mean IoU 0.538), `lulc_nyc`
on 90.2% (0.546), and `tim_nyc` with one unseeded draw of random sampler
weights on 89.5% (0.532). So
thinking in modalities adds nothing here, and it is not used
(`data/experimental/tim_check.json`).

### Weights read by the experiments

Every file below comes from its publisher's own Hugging Face repository at a
pinned commit. The PyTorch checkpoints are read with
`torch.load(..., weights_only=True)`, which admits tensors and an
`OrderedDict` and no code; each one's SHA-256 is the file's own hash, which
is also its Git LFS identifier. Nothing trained in these experiments is in
this repository: trained weights are saved as safetensors under the
git-ignored `outputs/` folder, and the owner decides what to publish.

| Model | Repository at commit | File | Format | SHA-256 | Used by |
|---|---|---|---|---|---|
| TerraMind 1.0 base | `ibm-esa-geospatial/TerraMind-1.0-base` at `fb96c70` | `TerraMind_v1_base.pt` | PyTorch, `weights_only=True` | `83c3a0938067c83867a46e564443c2fa38383bf4f966d931b11cb025b847d7ec` | the app's land-cover batch, `check_tim.py`, `train_cover.py` |
| TerraMind 1.0 small | `ibm-esa-geospatial/TerraMind-1.0-small` at `960f754` | `TerraMind_v1_small.pt` | PyTorch, `weights_only=True` | `755e9cce9483fd61334ef66c79f805406db5151a8b44a685c8fbbe023c684701` | `train_cover.py` |
| TerraMind 1.0 tiny | `ibm-esa-geospatial/TerraMind-1.0-tiny` at `2b5ac0a` | `TerraMind_v1_tiny.pt` | PyTorch, `weights_only=True` | `e56ea9ebcd4451078b9ca4893d5cd8a89bbee376ae16829c3e7fbbbc76de0eba` | `train_cover.py` |
| TerraMind-base-Flood | `ibm-esa-geospatial/TerraMind-base-Flood` at `1e4b242` | `TerraMind_v1_base_ImpactMesh_flood.pt` | PyTorch (a Lightning checkpoint of tensors), `weights_only=True` | `22627584c2db618c2f6ddb64b411a95762a893becb25104e3f66bfebecaa71e9` | `run_flood_ida.py`, `check_flood_impactmesh.py` |
| Granite TTM r3 | `ibm-granite/granite-timeseries-ttm-r3`, branch `1024-96-r3` at `c6da085` | safetensors | safetensors | not needed | `backtest_surge_candidates.py` |
| Granite FlowState r1.1 | `ibm-granite/granite-timeseries-flowstate-r1`, branch `r1.1` at `b80e0f1` | safetensors | safetensors | not needed | `backtest_surge_candidates.py` |
| Granite PatchTST-FM r2 | `ibm-granite/granite-timeseries-patchtst-fm-r2` at `b125275` | safetensors | safetensors | not needed | `backtest_surge_candidates.py` |
| Chronos-2 | `amazon/chronos-2` at `29ec376` | safetensors | safetensors | not needed | `backtest_surge_candidates.py`, `finetune_chronos2_surge.py` |

All are Apache-2.0 except PatchTST-FM r2, which its card offers under
OpenMDW 1.0 or Apache 2.0 at the user's choice.

## Inference energy

`app/emissions.py` records every LLM call in a briefing with its tokens,
duration and an energy status:

| Status | When |
|---|---|
| measured | Local endpoint on Apple Silicon with the `energy` extra (zeus-apple-silicon). Whole-chip energy during the call, so it includes other processes. |
| estimated | Local endpoint with `RIPRAP_ENERGY_WATTS` set: declared watts times duration. |
| unknown | Everything else. Hosted endpoints are always unknown and no per-query figure is reported for them. |

zeus-apple-silicon 1.1.0 reads 0 mJ of CPU energy on an Apple M5; those
readings are rejected and the call is marked unknown. The ledger is the
`emissions` block of every result. It covers the LLM only: the surge model
is 1.5 million parameters on CPU (about 0.2 J a call on an M3, by the
owner's reproduction), and the satellite models run in batch jobs, not in
a briefing.
The numbers in [`docs/history/BENCHMARKS.md`](history/BENCHMARKS.md) come from the
retired GPU stack and are historical. Details in
[`docs/EMISSIONS.md`](EMISSIONS.md).
