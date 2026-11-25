"""Portable inference for the Phase 3 artifact; no training or registry dependency."""
import numpy as np
import pandas as pd

RAW = ['Area','Bedrooms','Bathrooms','Age','Location','Property_Type']


def predict_bundle(bundle, frame):
    if not isinstance(frame, pd.DataFrame) or set(frame.columns) != set(RAW) or len(frame.columns) != len(RAW):
        raise ValueError('Expected exactly the six raw property features')
    x = frame[RAW].copy()
    for col in RAW[:4]:
        x[col] = pd.to_numeric(x[col], errors='raise')
    if x.empty or x.isna().any().any() or not np.isfinite(x[RAW[:4]].to_numpy()).all():
        raise ValueError('Empty, missing or nonfinite input')
    if (x[['Area','Bedrooms','Bathrooms']] <= 0).any().any() or (x.Age < 0).any():
        raise ValueError('Invalid area, room counts or age')
    if (x[['Bedrooms','Bathrooms','Age']] % 1 != 0).any().any():
        raise ValueError('Room counts and age must be integral')
    for col in RAW[4:]:
        x[col] = x[col].astype(str).str.strip()
        if x[col].eq('').any():
            raise ValueError('Blank category')
    x['Area_per_bedroom'] = x.Area / x.Bedrooms
    x['Bathrooms_per_bedroom'] = x.Bathrooms / x.Bedrooms
    if bundle['kind'] == 'mlp':
        p = bundle['estimator'].predict(bundle['preprocessor'].transform(x))
        p = bundle['target_scaler'].inverse_transform(np.asarray(p).reshape(-1,1)).ravel()
    elif bundle['kind'] == 'pipeline':
        p = bundle['estimator'].predict(x)
    else:
        raise ValueError('Unsupported Phase 3 bundle')
    p = np.maximum(np.asarray(p, dtype=float), 0)
    if not np.isfinite(p).all():
        raise ValueError('Nonfinite predictions')
    return p
