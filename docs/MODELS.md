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
after storms, one maps paved and green land.

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
and [paved and green land in QN12](https://msradam.github.io/riprap/gallery/qn12-paved/).

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
| TerraMind NYC adapters (`lulc_nyc`) | [`msradam/TerraMind-NYC-Adapters`](https://huggingface.co/msradam/TerraMind-NYC-Adapters) at `9843416`, on [`ibm-esa-geospatial/TerraMind-1.0-base`](https://huggingface.co/ibm-esa-geospatial/TerraMind-1.0-base) at `fb96c70` | in a batch job; the app reads the saved rasters | `eo`, for the batch only |

The author's weights are loaded from safetensors files at those commits.
The TerraMind base is published only as a PyTorch checkpoint; it is read
with `weights_only=True`, which admits tensors and no code. The models were
trained on AMD Developer Cloud and are reproduced independently at
[github.com/msradam/riprap-models](https://github.com/msradam/riprap-models).

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
(`scripts/backtest_surge_candidates.py`, run 2026-10-01,
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
2 of the 23 flood windows with no false alarm. That is better on every
measure, by a small margin, and it still misses 21 of the 23 floods, so the
sentence's real weakness stays. It is not in the app: the surge forecast
runs per request, so the server needs the weights, and these are on the
owner's machine only (`outputs/surge_models/chronos2_battery/`, 478 MB of
safetensors). Switching needs the owner to publish them, and adds the
`chronos-forecasting` package to the `ml` extra. A forecast takes about
0.03 s on CPU.

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

### TerraMind NYC adapters

The `lulc_nyc` adapter labels each 10 m pixel of a Sentinel-2 scene with
one of five classes. `scripts/run_landcover_batch.py` runs it on up to two
clear dates of a year between 15 June and 30 September, so every year is
mapped in full leaf. The year's map is the clearer date's map, and the
second date fills only the pixels the first could not see. (An earlier
version took a vote between the two dates. With two dates every
disagreement is a tie, and the tie went to the paved class.) Riprap reports
three groups: paved or built over, green (trees and grass), and water. A
comparison of two years uses only the pixels both years labelled.

| Question | Answered | How |
|---|---|---|
| How much of this district is paved or built over, and how much is green | Yes | Shares of the latest year's map |
| How has land cover changed here since a given year | Only as a difference held against the model's noise | The paved share in the first and last year mapped; a difference inside the noise is reported as no measurable change |
| If this paving trend continues, is runoff likely to rise here | No | Tested: differences beyond the noise are as frequent as the noise alone produces, so no trend is claimed. The shares are quoted and the sentence says so |
| Has new construction appeared in this area | No | See below |

Test, `scripts/run_landcover_batch.py`, run 2026-10-01: the 2021 map against
ESA WorldCover 2021 over the city's land. WorldCover is the adapter's own
label source, so this measures how well it reproduces its labels, not how
well it maps the ground.

| Measure | Result |
|---|---|
| Same class of the five | 82.2% of pixels |
| Same group of the three Riprap reports (paved, green, water) | 87.1% |
| WorldCover's green land that the model also calls green | 66.3% |
| WorldCover's pixels of each class given the same class | water 81.8%, built 97.5%, trees 42.8%, grass 68.5%, bare 14.8% |
| A district's paved share, model minus WorldCover | median 7.7 points, largest gap 19.0 |
| Agreement by borough | Bronx 80.7%, Brooklyn 86.4%, Manhattan 81.0%, Queens 83.3%, Staten Island 76.7% |

So it calls much green ground paved, trees most of all, and a district's
paved share reads about 8 points high. Every land-cover sentence says so.

The model's own noise: two dates of one year (2021-06-16 and 2021-09-29,
2026-06-20 and 2026-07-20), compared on the pixels both labelled. A
district's paved share differs by 0.8 points at the median and by under
3.7 points 19 times in 20. A neighbourhood's differs by 1.0 at the median and
under 5.8 19 times in 20. A district is held against 3.7; a neighbourhood and
an address (a 500 m circle) against 5.8. A difference between years inside
that is reported as no measurable change.

No trend is claimed. Between the first and the last year mapped, 3 of the 59
community districts differ by more than 3.7 points (MN09 by 5.5 and MN12 by
5.0 down, QN08 by 3.9 up). Noise alone would put about 3 of 59 beyond a
19-in-20 threshold. In MN09 and MN12 the 2018 map stands apart and the three
later years are level, which points at the 2018 image and not at the ground.
So a larger difference is stated with that caution, and nothing about runoff
follows from it. The saved results are in
`data/experimental/landcover.json`.

2018 and 2024 have one usable date each (the other clear dates covered only
part of the city), so those years have no second date to fill cloud gaps.
An earlier run mapped May scenes for 2026 and broke ties toward paved; both
were found in review and the batch was rerun.

Three things differ from the model card, each checked on one box of
Manhattan, Brooklyn and Queens against ESA WorldCover 2021 (one-off checks
of 2026-10-01; the results are in `data/experimental/landcover_checks.json`):

The classes are not the card's. The card lists impervious, vegetation,
water, bare or cropland, building. The training script
(`experiments/05_terramind_nyc_finetune/data/slice_and_label_nyc.py` at tag
`v0.7.0`) wrote water, built-up, trees and shrubs, grass and crops, other.
With the script's order the adapter agrees with WorldCover on 90.5% of
pixels. There is no building class.

Two of its three inputs carry nothing. The architecture takes Sentinel-2,
Sentinel-1 radar and elevation. Zeros for radar and elevation give the same
map (90.5%) as real data (89.6% with radar in decibels, 90.4% with radar as
the training code fed it). Training fed radar on a scale the model's
statistics do not match, and an empty elevation channel. Riprap reads
Sentinel-2 only.

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

Not built: new construction. The `buildings_nyc` adapter labels 57% of that
box as building, and between two dates of one year (2021-06-16 and
2021-09-29) 4.6% of pixels change label. New buildings cover far less than
that in a year, so a difference between two years would be the model's
noise. The city's building footprints and DOB permits are the record.

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
