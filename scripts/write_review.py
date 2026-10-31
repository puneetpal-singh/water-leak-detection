"""Record the review's measured changes without selecting models on 2019."""
from pathlib import Path
import pandas as pd

root = Path(__file__).resolve().parents[1]
before = pd.read_csv(root/'results/review_v1_comparison.csv')
after = pd.read_csv(root/'results/model_comparison.csv')
columns = ['method','pr_auc_ap','f1','leaks_detected','false_alarms','mean_delay_hours']
comparison = before[columns].merge(after[columns],on='method',suffixes=('_v1','_v2'))
comparison.to_csv(root/'results/review_comparison.csv',index=False)
rows = []
for m in comparison.itertuples():
    rows.append(f'| {m.method} | {m.leaks_detected_v1} → {m.leaks_detected_v2} | {m.false_alarms_v1} → {m.false_alarms_v2} | {m.f1_v1:.3f} → {m.f1_v2:.3f} | {m.mean_delay_hours_v1:.1f} → {m.mean_delay_hours_v2:.1f} |')
report = '''# Correctness and completeness review

The review found issues worth fixing. Protocol v2 corrects calibration and edge
cases; it does not claim that the detectors are ready for operational deployment.
The existing restrained /unslop design is retained. Added charts answer evaluation
questions rather than decorate the interface.

## Findings and fixes

1. **LOF novelty calibration used fitted rows.** The original call scored every
   row with `score_samples`, including some LOF fit samples. Scikit-learn warns
   against using novelty scoring on fitted samples. Version 2 uses the earliest
   80% of eligible 2018 rows as a fitting pool and the last 20% as an unseen,
   chronologically later threshold reference. All transforms, sensor MAD scales,
   IQR fences and models fit only the selected fitting-pool rows. Historical fit
   rows use LOF's `negative_outlier_factor_` for descriptive output only. No fit
   row contributes to threshold percentiles.
2. **Missing data were treated as normal by alarm clearing.** Missing scores
   now interrupt confirmation and clearance counts and cannot clear an unresolved
   alarm. Timestamp gaps also break consecutive-sample counts. This changes no
   actual complete-source-data alarm solely due to missingness.
3. **A shifted grid could be accepted as five-minute sampling.** Absolute grid
   alignment is now checked. Identical duplicates containing missing cells are
   accepted; conflicting duplicates still fail. Unsupported feature frequencies
   fail explicitly instead of silently changing lag meanings.
4. **Event matching relied on input order.** Events and alarm starts are now
   sorted before one-to-one matching. Empty-event periods keep a valid table schema.
5. **Cached telemetry could become stale after raw-file changes.** Experiment
   reruns verify source checksums and rebuild telemetry. A separate artifact check
   verifies provenance, fit/reference chronology, calibration, saved results and
   all browser sensor histories.
6. **Slow browser requests could update a newer view.** Route-version guards
   discard stale responses. Invalid dates clear old charts. Removed Plotly graphs
   are purged when navigating. Three Node tests cover these behaviours.
7. **Several requested visualization types were absent.** Added precision–recall
   curves, onset/confirmation timelines and train-versus-benchmark feature
   distributions. The notebooks now contain guided analysis and real executed
   outputs, with an optional reproducible notebook runtime.

LOF reference: [scikit-learn novelty detection guidance](https://scikit-learn.org/stable/modules/outlier_detection.html#novelty-detection-with-local-outlier-factor).

## Results changed; the trade-off is explicit

Before values are from Git commit `05356ef6c995c39fdbe2308c678d4662aaafb04e`.
The snapshot is preserved in `results/review_v1_comparison.csv`. Version 2 changes
the fitting/reference protocol, so this is not a controlled single-model ablation.
The 2019 benchmark had already been inspected; it is no longer described as an
untouched external test. Percentile selection still uses only 2018 validation.
No new search against 2019 outcomes was performed.

| Method | Events / 19, v1 → v2 | Unmatched alarms, v1 → v2 | Point F1, v1 → v2 | Mean delay h, v1 → v2 |
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+'''

For PCA, fewer unmatched alarms come with more misses and longer delay. Point
F1 decreases. High recall for IQR and Isolation Forest still comes with hundreds
of unmatched alarms. The shift control remains essential; none of these results
establish deployment reliability.

## Coverage against the original brief

| Area | Evidence and scope |
|---|---|
| Real data, dictionary, units and quality | Verified official source files; inventory, dictionary and audit |
| Cleaning and alignment | Reusable preprocessing; no imputation needed for the actual files |
| EDA and interpretation | Hourly/weekday/weekend profiles, weekly/monthly trends, distributions, correlations and local event changes |
| Leak comparisons | Before/onset/recovery windows; overlap and record-end censoring documented |
| Causal features | Trailing statistics, lags, daily residuals, contrasts and weekly changes; future-invariance tests |
| Statistical and ML methods | Robust MAD, IQR, Isolation Forest, PCA and novelty LOF |
| Leak event logic | Sensor gate, persistence, clearance, no backdating, one-to-one matching |
| Evaluation | Point metrics, AP, delays, misses, false alarms, horizon sensitivity and timing controls |
| Explainability | Signed sensor residual departures; explicitly not causal localization or ML feature importance |
| Interactive dashboards | Seven web views and six Streamlit workbench views |
| Visualizations | Nine standalone figures, including added PR curves, event timeline and feature distributions |
| Reusable code and notebooks | Modular pipeline; four guided, executed notebooks |
| Code quality and reproducibility | Config, fixed seed, pinned core/optional dependencies, tests and source verification |
| Presentation | README, workflow diagram, real screenshots, methodology and walkthrough |
| CV output | Three bullets using actual dataset/features/scope, without inflated performance claims |

## Verification

- 22 Python regression cases passed.
- Three Node browser-logic tests passed; JavaScript syntax passed.
- All six Streamlit views passed AppTest.
- All four notebooks executed successfully and contain genuine outputs.
- Artifact verification passed: 119 sensor histories, 33 event windows, 95
  event/method rows, saved metrics and reference thresholds.
- Browser review exercised revised metrics, PR curves, timeline method selection,
  invalid dates, event sensor selection and methodology labels.

## Remaining limits and worthwhile next work

The main limitation is detector reliability, not missing dashboard polish. Only
two validation onsets support calibration. Stable fitting states contain ongoing
leaks; a rolling reference absorbs gradual changes. There is one simulated network
and one evaluation year. An additional untouched network or year is needed before
further model tuning can yield credible generalization claims. Pump-state and
demand-conditioned baselines, operational false-alarm budgets and hydraulic
localization remain future experiments, not completed capabilities.
'''
(root/'docs/review.md').write_text(report,encoding='utf-8')
print('Generated review report and before/after comparison')
