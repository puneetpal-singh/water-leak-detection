# What this experiment measures

The objective is detecting a **new leak onset within 72 hours**, with an alarm
that could have been generated at that time. This is not pipe localization or
the original BattLeDIM competition's economic score.

## Data cleaning

Read semicolon-separated, decimal-comma CSVs with the explicit timestamp format.
Timestamps are timezone-naive because the source does not specify a timezone;
never infer UTC or add daylight-saving adjustments. Sort and align on the 5-minute
grid. Drop only identical duplicate rows; reject conflicting duplicates and
off-grid timestamps. Flag negative readings; retain signed flow and negative
pressure because their validity depends on hydraulic context. Negative demands
and nonfinite values become missing. Forward-fill at most two 5-minute samples;
leave longer gaps missing and exclude incomplete feature rows from scoring.
The downloaded files require **no imputation**. Raw data are never rewritten.

Modeling aggregates completed 15-minute bins, labeled at availability time.
For example, 00:15 contains measurements at 00:00, 00:05 and 00:10. The source
pressure values are themselves five-minute averages, per the dataset documentation.
The original measurements remain available in the sensor explorer and EDA tables.

## Chronological split and contamination

Fit: January–September 2018, after feature warmup, excluding seven days either
side of known historical onsets and three days either side of historical repairs.
Validation: October–December 2018. Test: January–December 2019.
2019 event labels never enter training selection, feature construction or calibration.

Only about 2.2% of 2018 is free of *all* simulated leaks. The first leak begins
January 8, leaving too little leak-free history to represent seasonal operation.
The selected training set therefore represents **stable operating states with
existing background leaks**, not certified normal, leak-free data. This is a
change-detection experiment. A clean-normal hydraulic model would be another study.

## Features and models

Pressure, flow and level are the model inputs. Demand meters are analysed in EDA
but omitted from the first detector to keep instrumentation requirements small.
Each sensor contributes its residual from the median of the preceding seven days
at the same quarter-hour (at least five days required), trailing residual mean,
one-hour difference, standard deviation, range, lagged residual and weekly change.
Two extra features compare real sensor pairs; no adjacency or conservation claim
is made for those pairs. Weekly lag creates a seven-day warmup.

All trailing statistics end at the present completed bin. The rolling reference
updates from *past measurements*, including during test; fitted model parameters,
scales and thresholds stay frozen. This causal adaptation can absorb slow leaks
and reduce sensitivity to gradual onsets.

RobustScaler fits only eligible training rows. Features with negligible training
variation are dropped; transformed values clip to [-25, 25] to bound extreme
inputs. Models fit a fixed seeded sample of up to 6,000 eligible training rows.
The robust baseline averages the three largest absolute sensor residual MAD
z-scores (MAD scale floor 0.01 in each sensor's units), without score clipping.
The IQR baseline averages exceedances
beyond training Tukey fences. Isolation Forest uses 200 trees; PCA retains 95%
of training variance and scores reconstruction MSE; novelty LOF uses 35 neighbours.
The robust baseline uses the residual subset; the other four methods use the
full shared feature matrix. All methods use the same input sensor channels and
alarm policy. Deep learning is not needed for this comparison.

## Thresholds and streaming alarms

Candidate thresholds are the 95th, 97.5th, 99th, 99.5th and 99.9th percentiles of
training scores. Choose by validation **event F1**, then fewer unmatched alarms,
then the larger quantile. This small validation set contains only two new onsets,
so threshold choice is uncertain; every candidate is saved for review.

An exceedance also requires at least two sensors with absolute residual robust-z
above 2.5, using training median and MAD. An alarm emits after four consecutive
15-minute exceedances. Its timestamp is the confirmation time, not the start of
the run. Clear after four consecutive non-exceedances to suppress chatter.
The persistence and clearance values are fixed before test, not optimized on 2019.

## Evaluation

Point positives are timestamps from onset through min(onset + 72h, repair).
All other timestamps are negative **for new-onset detection**, including ongoing
leaks and repairs. Precision, recall and F1 use the emitted alarm's active state.
PR-AUC is reported as average precision of the raw anomaly score, before sensor
gating and persistence; the positive prevalence provides the no-skill reference.

Event matching is chronological and one-to-one: one new alarm start may match
one onset only, during its 72-hour window. An alarm active before an onset does
not detect it. Unmatched alarm starts are false alarms *relative to this task*;
they may reflect a repair, a persistent leak, a pump change or another hydraulic
change. Carryover 2018 leaks are not counted as new 2019 events. Misses have no
delay value. Mean and median delay include detected events only, so always read
them with event recall. Boundary-censored active alarms are marked in the export.

To check whether a high alarm count alone explains event recall, a seeded
negative control shifts alarm starts around the 2019 calendar 200 times, preserving
their count and relative spacing. The mean and 5th–95th percentile recall are saved.
This is descriptive, not a significance test: seasonal nonstationarity remains.
Fixed-threshold sensitivity at 24, 72 and 168 hours is exported without retuning.

## Engineering attribution and limits

At alarm confirmation, rank signed residual robust-z values by sensor. These
explain sensor departures; they are **not** Isolation Forest feature importances,
causal pipe diagnoses or SHAP explanations. Before/onset/recovery medians are
retrospective descriptive comparisons, confounded by diurnal demand and overlapping
leaks. Many events continue to the record's end and have no observed recovery.

The data are realistic **simulated** telemetry, not a deployed utility trial.
There is one network, one test year and no independent geographic holdout.
Seasonal drift, short validation history, sustained leaks and rolling-reference
adaptation limit conclusions. No official competition ranking is claimed.
