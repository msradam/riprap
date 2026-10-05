---
license: apache-2.0
base_model: ibm-granite/granite-timeseries-ttm-r2
library_name: granite-tsfm
pipeline_tag: time-series-forecasting
tags:
  - time-series
  - storm-surge
  - tide-gauge
  - noaa
  - nyc
  - granite
  - ttm
---

# Granite-TTM-r2-Battery-Surge

<!-- Corrected card, written 2026-10-05. Its source is
docs/model-cards/Granite-TTM-r2-Battery-Surge.md in the Riprap repository. -->

A fine-tune of IBM Granite TimeSeries TTM r2 (2.96 million parameters) on
the surge residual at NOAA tide gauge 8518750 (The Battery, lower
Manhattan). It reads 1,024 hourly values of the residual (observed water
level minus NOAA's predicted tide) and writes the next 96. Apache 2.0.

**Status: experimental, and not recommended for use.** On data after its
training period it does not beat a one-line rule, and it does not foresee
floods. Riprap took it out of its default briefings on 2026-10-05.

## Result on held-out data

The test is `scripts/backtest_surge.py` in
[msradam/riprap](https://github.com/msradam/riprap), run 2026-10-05, with
its output in `data/experimental/surge.json`. It scores 639 windows, one a
day from 2025-01-01 to 2026-10-01. The training data ends 2024-12-31, so
no scored hour was used to train the model or to choose its checkpoint.
Truth is the gauge. The baselines need no model; the two that have a
fitted part (the damping, the monthly means) were fitted on 2015 to 2024
only.

| Forecast | Mean absolute error over 96 hours | Model minus this, 95% interval |
|---|---|---|
| This model | 0.115 m | |
| Last value fading toward the mean of the 1,024 input hours (damped persistence, 0.97 per hour) | 0.108 m | +0.007 m (+0.003 to +0.010) |
| Mean residual of the calendar month, 2015 to 2024 | 0.116 m | -0.002 m (-0.006 to +0.004) |
| Mean of the 1,024 input hours held | 0.119 m | -0.004 m (-0.008 to +0.000) |
| Last value held (persistence) | 0.133 m | -0.018 m (-0.026 to -0.012) |
| Mean of the last 24 hours held | 0.134 m | -0.019 m (-0.026 to -0.011) |
| Zero residual (the tide table alone) | 0.167 m | -0.053 m (-0.066 to -0.040) |

The intervals come from resampling the windows in runs of 14 days, since
windows a day apart share three of their four days. The model is worse
than damped persistence, with an interval clear of zero, and is not
distinguishable from the month's usual value or the mean of its own input.

It does not foresee floods. The water reached the gauge's minor flood
stage (7.0 ft above MLLW) in 23 windows, which are 5 distinct events
(hours at the stage less than 48 hours apart count as one; 6 if the two
tides of 22 and 23 August 2025 are counted apart). The model's total
reached the stage in 1 of the 23 windows, 1 of the 5 events, with 1 false
alarm. Damped persistence did the same with no false alarm. Holding the
last value reached it in 5 windows and 3 events, with 4 false alarms.

The observed residual peaked at 0.5 m or more in 92 windows (20 events).
The model forecast such a peak in 7 of them (5 events); holding the last
value did in 8 (6 events).

## Figures this card withdraws

Earlier versions of this card reported a 41.4% improvement in mean
absolute error over persistence (0.109 m against 0.186 m). That figure is
from the training run's own test split, the last 15% of 2015 to 2024, on
hourly means, against the last value held and no other baseline. On the
held-out windows above the margin over the last value held is about 14%, and the
model loses to damped persistence. The 41.4% figure should not be quoted.

Earlier versions said Hurricane Ida "falls within the test window". With a
70/15/15 split of 2015 to 2024 in time order, the test part starts in mid
2023, so Ida (September 2021) is in the training part. Ida in New York was
also a rainfall flood, not a surge. Earlier versions gave the size as 1.5
million parameters; the published safetensors file holds 2,964,960.

A table that split 40 windows by storm size, and a ten-case probe, are
left out of this card: neither has been rerun against the baselines above.

## Training data

- Source: NOAA CO-OPS station 8518750 (The Battery, NY), verified water
  level and harmonic tide predictions
- Range: 2015-01-01 to 2024-12-31, 6-minute values resampled to hourly
  means, 87,672 hours
- Split in time order: the first 70% of windows to train, the next 15% to
  choose the checkpoint, the last 15% (mid 2023 to 2024) as the run's test
- Residual standard deviation: 0.224 m

One caution on the held-out test: it reads the gauge's value at the top of
each hour, while training used hourly means.

## Architecture and training

| | |
|---|---|
| Backbone | TinyTimeMixer r2, revision `1024-96-r2` |
| Context and horizon | 1,024 hours in, 96 hours out, one channel |
| Parameters | 2,964,960 (backbone 2,009,536; decoder 758,720; head 196,704) |
| Fine-tune | all weights, AdamW at 1e-4, batch 64, up to 20 epochs, early stopping on validation loss, seed 42 |
| Framework | granite-tsfm 0.3.6, transformers 4.57 |
| Hardware | one AMD Instinct MI300X on AMD Developer Cloud, about 10 minutes |

## Use

```python
from tsfm_public import TinyTimeMixerForPrediction
from huggingface_hub import snapshot_download
import torch

path = snapshot_download("msradam/Granite-TTM-r2-Battery-Surge",
                         revision="181b892bf4c4693018a834d359427c279b315213")
model = TinyTimeMixerForPrediction.from_pretrained(path, use_safetensors=True).eval()
past = torch.tensor(residuals_m, dtype=torch.float32).reshape(1, 1024, 1)
with torch.no_grad():
    forecast = model(past_values=past).prediction_outputs.reshape(-1)  # 96 hours, metres
```

## Limits

- It has no wind or pressure input, so it cannot see a storm that has not
  reached the gauge. The surge forecasts to rely on are the National
  Weather Service's, NOAA's ETSS and the Stevens Flood Advisory System.
- It was trained on The Battery only.
- It is one training run with one seed.
- It forecasts 96 hours. It says nothing about sea level rise.

## License

Apache 2.0. The NOAA gauge data is in the U.S. public domain.

## Citation

```bibtex
@misc{granite-ttm-2024,
  title={Tiny Time Mixers (TTM): Fast Pre-trained Models for Enhanced Zero/Few-Shot Forecasting of Multivariate Time Series},
  author={Ekambaram, Vijay and others},
  year={2024},
  publisher={IBM Research},
}
```
