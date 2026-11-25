"""MLflow PythonModel wrapper. Load only trusted, locally generated artifacts."""
import hashlib
from pathlib import Path
import joblib
from mlflow.pyfunc import PythonModel
from phase4_inference import predict_bundle


class PropertyPredictor(PythonModel):
    def __init__(self, expected_sha256):
        self.expected_sha256 = expected_sha256

    def load_context(self, context):
        path = Path(context.artifacts['bundle'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != self.expected_sha256:
            raise ValueError('Registered model artifact hash mismatch')
        self.bundle = joblib.load(path)

    def predict(self, context, model_input, params=None):
        return predict_bundle(self.bundle, model_input)
