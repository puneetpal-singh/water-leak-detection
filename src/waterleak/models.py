"""Small model comparison using the same features, split and alarm policy."""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.preprocessing import RobustScaler

def fit_and_score(features: pd.DataFrame, fit_mask: pd.Series, seed: int = 42,
                  sample_limit: int = 6000) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Fit transforms and estimators on training data only; score higher as abnormal."""
    fit = features.loc[fit_mask]
    medians = fit.median()
    keep = fit.std().gt(1e-8) & medians.notna()
    fit, full = fit.loc[:, keep], features.loc[:, keep]
    medians = medians[keep]
    scaler = RobustScaler(quantile_range=(25, 75))
    train_scaled = scaler.fit_transform(fit.fillna(medians))
    all_scaled = scaler.transform(full.fillna(medians))
    # Clipping is fixed, symmetric and shared. Raw physical measurements stay intact.
    train_scaled = np.clip(train_scaled, -25, 25).astype('float32')
    all_scaled = np.clip(all_scaled, -25, 25).astype('float32')
    rng = np.random.default_rng(seed)
    selected = np.sort(rng.choice(len(fit), min(sample_limit, len(fit)), replace=False))
    sample = train_scaled[selected]
    absolute = np.abs(all_scaled)
    # Each model shares the multi-sensor persistence gate in the pipeline.
    scores = pd.DataFrame(index=features.index)
    scores['Robust baseline'] = np.nan  # Assigned from sensor MAD residuals below.
    q1, q3 = np.quantile(train_scaled, [0.25, 0.75], axis=0)
    excess = np.maximum(all_scaled - (q3 + 1.5 * (q3 - q1)), (q1 - 1.5 * (q3 - q1)) - all_scaled)
    scores['IQR baseline'] = np.maximum(excess, 0).mean(axis=1)
    forest = IsolationForest(n_estimators=200, max_samples=512, random_state=seed, n_jobs=-1)
    forest.fit(sample)
    scores['Isolation Forest'] = -forest.score_samples(all_scaled)
    pca = PCA(n_components=0.95, svd_solver='full')
    pca.fit(sample)
    reconstructed = pca.inverse_transform(pca.transform(all_scaled))
    scores['PCA reconstruction'] = ((all_scaled - reconstructed) ** 2).mean(axis=1)
    lof = LocalOutlierFactor(n_neighbors=35, novelty=True, n_jobs=-1)
    lof.fit(sample)
    # Chunking limits distance-matrix memory without changing the scores.
    scores['Local Outlier Factor'] = np.concatenate([-lof.score_samples(a) for a in np.array_split(all_scaled, 24)])
    valid = features.notna().all(axis=1)
    scores.loc[~valid] = np.nan
    # Signed residual robust-z is an engineering attribution, not an ML feature importance.
    residual_columns = [c for c in features if c.endswith('|residual')]
    r = features[residual_columns]
    center = r.loc[fit_mask].median()
    mad = (r.loc[fit_mask] - center).abs().median() * 1.4826
    sensor_z = (r - center) / mad.clip(lower=0.01)
    sensor_z.columns = [c.split('|')[0] for c in sensor_z]
    # Sensor-level MAD avoids zero-IQR rolling range features dominating this
    # interpretable baseline. Do not clip the statistic at a threshold plateau.
    scores['Robust baseline'] = np.sort(sensor_z.abs().to_numpy(), axis=1)[:, -3:].mean(axis=1)
    scores.loc[~valid] = np.nan
    metadata = {'feature_count': int(keep.sum()), 'training_rows': len(fit),
                'sample_rows': len(sample), 'pca_components': int(pca.n_components_),
                'pca_explained_variance': float(pca.explained_variance_ratio_.sum()),
                'feature_columns': full.columns.tolist(), 'valid_rows': int(valid.sum()),
                'training_feature_medians': medians.to_dict()}
    return scores, sensor_z, metadata
