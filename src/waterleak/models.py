"""Small model comparison using the same features, split and alarm policy."""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

def fit_and_score(features: pd.DataFrame, fit_mask: pd.Series, seed: int = 42,
                  sample_limit: int = 6000, reference_fraction: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fit transforms and estimators on training data only; score higher as abnormal."""
    eligible = features.loc[fit_mask].dropna()
    if not 0 < reference_fraction < 1 or sample_limit < 2 or len(eligible) < 10:
        raise ValueError('Need at least 10 complete training rows, a positive sample limit and a reference fraction in (0, 1)')
    # Chronologically later 2018 stable rows are never passed to fit, including
    # imputation, scaling, MAD, IQR fences and feature selection.
    boundary = int(len(eligible) * (1 - reference_fraction))
    pool, reference = eligible.iloc[:boundary], eligible.iloc[boundary:]
    rng = np.random.default_rng(seed)
    selected = np.sort(rng.choice(len(pool), min(sample_limit, len(pool)), replace=False))
    fit = pool.iloc[selected]
    medians = fit.median()
    keep = fit.std().gt(1e-8) & medians.notna()
    if not keep.any():
        raise ValueError('No varying training features remain')
    fit, full = fit.loc[:, keep], features.loc[:, keep]
    medians = medians[keep]
    scaler = RobustScaler(quantile_range=(25, 75))
    train_scaled = scaler.fit_transform(fit.fillna(medians))
    all_scaled = scaler.transform(full.fillna(medians))
    # Clipping is fixed, symmetric and shared. Raw physical measurements stay intact.
    train_scaled = np.clip(train_scaled, -25, 25).astype('float32')
    all_scaled = np.clip(all_scaled, -25, 25).astype('float32')
    sample = train_scaled
    # Each model shares the multi-sensor persistence gate in the pipeline.
    scores = pd.DataFrame(index=features.index)
    scores['Robust baseline'] = np.nan  # Assigned from sensor MAD residuals below.
    q1, q3 = np.quantile(train_scaled, [0.25, 0.75], axis=0)
    excess = np.maximum(all_scaled - (q3 + 1.5 * (q3 - q1)), (q1 - 1.5 * (q3 - q1)) - all_scaled)
    scores['IQR baseline'] = np.maximum(excess, 0).mean(axis=1)
    forest = IsolationForest(n_estimators=200, max_samples=min(512, len(sample)), random_state=seed, n_jobs=-1)
    forest.fit(sample)
    scores['Isolation Forest'] = -forest.score_samples(all_scaled)
    pca = PCA(n_components=0.95, svd_solver='full')
    pca.fit(sample)
    reconstructed = pca.inverse_transform(pca.transform(all_scaled))
    scores['PCA reconstruction'] = ((all_scaled - reconstructed) ** 2).mean(axis=1)
    lof = LocalOutlierFactor(n_neighbors=min(35, len(sample) - 1), novelty=True, n_jobs=-1)
    lof.fit(sample)
    # Chunking limits distance-matrix memory without changing the scores.
    fit_positions = features.index.get_indexer(fit.index)
    unseen_positions = np.flatnonzero(~features.index.isin(fit.index))
    lof_scores = np.full(len(features), np.nan)
    for batch in np.array_split(unseen_positions, min(24, max(1, len(unseen_positions)))):
        if len(batch):
            lof_scores[batch] = -lof.score_samples(all_scaled[batch])
    # Fit-row LOF factors are descriptive only; reference and holdouts use novelty scores.
    lof_scores[fit_positions] = -lof.negative_outlier_factor_
    scores['Local Outlier Factor'] = lof_scores
    valid = features.notna().all(axis=1)
    scores.loc[~valid] = np.nan
    # Signed residual robust-z is an engineering attribution, not an ML feature importance.
    residual_columns = [c for c in features if c.endswith('|residual')]
    r = features[residual_columns]
    center = r.loc[fit.index].median()
    mad = (r.loc[fit.index] - center).abs().median() * 1.4826
    sensor_z = (r - center) / mad.clip(lower=0.01)
    sensor_z.columns = [c.split('|')[0] for c in sensor_z]
    # Sensor-level MAD avoids zero-IQR rolling range features dominating this
    # interpretable baseline. Do not clip the statistic at a threshold plateau.
    scores['Robust baseline'] = np.sort(sensor_z.abs().to_numpy(), axis=1)[:, -3:].mean(axis=1)
    scores.loc[~valid] = np.nan
    metadata = {'feature_count': int(keep.sum()), 'training_rows': len(eligible),
                'sample_rows': len(sample), 'pca_components': int(pca.n_components_),
                'pca_explained_variance': float(pca.explained_variance_ratio_.sum()),
                'feature_columns': full.columns.tolist(), 'valid_rows': int(valid.sum()),
                'training_feature_medians': medians.to_dict(),
                'estimator_fit_row_positions': fit_positions.tolist(),
                'threshold_reference_row_positions': features.index.get_indexer(reference.index).tolist(),
                'threshold_reference_rows': len(reference),
                'estimator_fit_last': str(fit.index.max()),
                'threshold_reference_start': str(reference.index.min()),
                'threshold_reference_end': str(reference.index.max())}
    return scores, sensor_z, metadata
