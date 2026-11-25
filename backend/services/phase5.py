"""Phase 5 registry-backed inference and training-only aggregate analytics."""
import hashlib
import json
from pathlib import Path
import sys
from threading import Lock
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ['Area', 'Bedrooms', 'Bathrooms', 'Age', 'Location', 'Property_Type']
MODEL = 'RealEstatePricePredictor'
UNITS = 'unspecified source units'

class DomainError(ValueError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def training_data(root):
    root = Path(root)
    manifest = read(root/'data/processed/split_manifest.json')
    path = root/'data/processed/train.csv'
    source = manifest['source_sha256']
    if sha(root/'data/raw/house_prices.csv') != source:
        raise ValueError('House dataset hash mismatch; restore the original data')
    if sha(path) != manifest['partitions']['train']['sha256']:
        raise ValueError('Training partition hash mismatch; rerun Phase 2')
    frame = pd.read_csv(path)
    if len(frame) != manifest['partitions']['train']['rows'] or frame.empty:
        raise ValueError('Training partition row count mismatch')
    if not set(RAW+['Price']).issubset(frame.columns) or frame[RAW+['Price']].isna().any().any():
        raise ValueError('Invalid training data schema or missing values')
    if not np.isfinite(frame[RAW[:4]+['Price']].to_numpy(dtype=float)).all():
        raise ValueError('Nonfinite training data')
    return frame, source


class PredictionService:
    def __init__(self, predictor, frame, model_version, selected_model, source_sha256):
        self.predictor = predictor
        self.version = str(model_version)
        self.selected_model = selected_model
        self.source_sha256 = source_sha256
        self.frame = frame.copy()
        self.lock = Lock()
        self.categories = {c: sorted(str(v) for v in frame[c].unique()) for c in RAW[4:]}
        self.ranges = {c: {'min': float(frame[c].min()), 'max': float(frame[c].max())} for c in RAW[:4]}

    def info(self):
        return {'model_name': MODEL, 'model_version': self.version, 'selected_model': self.selected_model,
                'loaded_from_alias': 'champion', 'source_sha256': self.source_sha256,
                'raw_features': RAW, 'categories': self.categories, 'training_ranges': self.ranges,
                'units': UNITS, 'training_rows': len(self.frame), 'reload_policy': 'Restart API after alias changes'}

    def predict(self, properties):
        rows = [p.model_dump() for p in properties]
        if not rows or len(rows)>100:
            raise DomainError('Batch size must be 1–100')
        for i, row in enumerate(rows):
            for col, values in self.categories.items():
                if row[col] not in values:
                    raise DomainError(f'Property {i+1}: {col} must be one of {", ".join(values)}')
            for col, limits in self.ranges.items():
                if not limits['min'] <= row[col] <= limits['max']:
                    raise DomainError(f'Property {i+1}: {col} outside supported training range {limits["min"]}–{limits["max"]}')
        with self.lock:
            values = np.asarray(self.predictor.predict(pd.DataFrame(rows, columns=RAW)), dtype=float)
        if values.shape != (len(rows),) or not np.isfinite(values).all() or (values<0).any():
            raise RuntimeError('Model returned invalid predictions')
        return [{'predicted_price': round(float(v), 2), 'units': UNITS, 'model_name': MODEL,
                 'model_version': self.version, 'warnings': ['Estimate from local historical sample; not a verified market valuation.']} for v in values]

    def market(self):
        def groups(col):
            out=[]
            for name, group in self.frame.groupby(col, sort=True):
                if len(group)<5: continue
                out.append({'category': str(name), 'count': len(group),
                            'median_price': round(float(group.Price.median()),2),
                            'mean_price': round(float(group.Price.mean()),2)})
            return out
        return {'scope': 'training partition only; descriptive sample, not live market data', 'units': UNITS,
                'sample_size': len(self.frame), 'mean_price': round(float(self.frame.Price.mean()),2),
                'median_price': round(float(self.frame.Price.median()),2),
                'by_location': groups('Location'), 'by_property_type': groups('Property_Type'),
                'minimum_group_size': 5}


def load_service(root=ROOT):
    root = Path(root).resolve()
    db = root/'mlruns/phase4.sqlite'
    if not db.is_file():
        raise FileNotFoundError('Phase 4 registry missing. Run python scripts/run_phase4.py prepare first.')
    frame, source = training_data(root)
    path = str(root/'ml-pipeline/registry')
    if path not in sys.path: sys.path.insert(0,path)
    from phase4 import configure
    mlflow, client, _, _ = configure(root)
    mv = client.get_model_version_by_alias(MODEL, 'champion')
    if mv.status != 'READY' or not mv.tags.get('phase4_import_id'):
        raise ValueError('Champion is not a ready Phase 4 registered model')
    if mv.tags.get('source_sha256') != source:
        raise ValueError('Champion dataset differs from current training dataset')
    if not mv.tags.get('selected_model'):
        raise ValueError('Champion selected_model tag missing')
    # Use exact resolved version, not a moving alias. Trusted local registry only.
    predictor = mlflow.pyfunc.load_model(f'models:/{MODEL}/{mv.version}')
    service = PredictionService(predictor, frame, mv.version, mv.tags['selected_model'], source)
    smoke = np.asarray(predictor.predict(frame[RAW].head(3)),dtype=float)
    if smoke.shape != (min(3,len(frame)),) or not np.isfinite(smoke).all() or (smoke<0).any():
        raise ValueError('Champion smoke test failed')
    return service
