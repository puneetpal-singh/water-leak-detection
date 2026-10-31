# Step-by-step project walkthrough

Each stage leaves reviewable code and measured outputs. Run the commands in the
README from the repository root, then use these files to follow the analysis.

| Step | Work completed | Evidence |
|---|---|---|
| 1 | Inspect official files and source units | source_inventory.csv, data_dictionary.csv |
| 2 | Verify checksums, align timestamps, audit quality | download_data.py, data_audit.json |
| 3 | Study daily, weekday, weekly and monthly behaviour | *_profiles.csv, *_means.csv |
| 4 | Build trailing features with no future inputs | features.py, test_features.py |
| 5 | Establish robust MAD and IQR baselines | models.py |
| 6 | Compare Isolation Forest, PCA and novelty LOF | model_comparison.csv |
| 7 | Group score exceedances into persistent alarms | evaluation.py, alarm_episodes.csv |
| 8 | Evaluate points and one-to-one event matches | event_detections.csv, horizon_sensitivity.csv |
| 9 | Rank sensor departures and interpret changes | signed_residual_z, event_sensor_changes.csv |
| 10 | Compare delays, misses, false alarms and timing controls | model_comparison.csv, validation_calibration.csv |
| 11 | Build web and Streamlit investigation interfaces | dashboard/ |
| 12 | Export focused interactive figures | results/figures/ |
| 13 | Keep reusable modules separate from four notebooks | src/waterleak/, notebooks/ |
| 14 | Test cleaning, causality, fitting and event logic | tests/, check_dashboard.py |
| 15 | Write reproducible methodology and results | README.md, methodology.md |
| 16 | Present engineering findings and limitations | Engineering Insights, design.md |
| 17 | Produce three defensible CV bullets | results/cv_bullets.md |

The study deliberately reports poor alarm reliability. A portfolio discussion
should explain why all of 2019 is leak-positive, why onset detection is a different
task, why delays cannot be backdated, and why frequent alarms can inflate recall.
