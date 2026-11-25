"""Additive Phase 5 router, separate from the foundation app."""
import logging
import secrets
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from backend.schemas.phase5 import PropertyInput, BatchInput, Prediction, BatchPrediction
from backend.services.phase5 import DomainError
from backend.services.datasets import dataset_status

log = logging.getLogger(__name__)


def make_router(service, api_key, root):
    router = APIRouter(prefix='/api/v1')
    header = APIKeyHeader(name='X-API-Key', auto_error=False)

    def authorize(key: str | None = Security(header)):
        if not key or not secrets.compare_digest(key.encode('utf-8'),api_key.encode('utf-8')):
            raise HTTPException(401, detail='Missing or invalid API key')

    auth = [Depends(authorize)]

    @router.get('/health', tags=['System'])
    def health():
        return {'status':'ok','version':'0.5.0','phase':'prediction','model_ready':True}

    @router.get('/datasets', dependencies=auth, tags=['System'])
    def datasets():
        return {'datasets':dataset_status(root)}

    @router.get('/model/info', dependencies=auth, tags=['Model'])
    def info():
        return service.info()

    def predict(properties):
        try:
            return service.predict(properties)
        except DomainError as exc:
            raise HTTPException(422, detail=str(exc)) from None
        except Exception:
            log.exception('Prediction failed')
            raise HTTPException(503, detail='Prediction unavailable') from None

    @router.post('/predict', response_model=Prediction, dependencies=auth, tags=['Predictions'], responses={401:{'description':'Missing or invalid API key'},422:{'description':'Invalid property input'},503:{'description':'Prediction unavailable'}})
    def single(body: PropertyInput):
        return predict([body])[0]

    @router.post('/predict/batch', response_model=BatchPrediction, dependencies=auth, tags=['Predictions'], responses={401:{'description':'Missing or invalid API key'},422:{'description':'Invalid batch or property input'},503:{'description':'Prediction unavailable'}})
    def batch(body: BatchInput):
        results = predict(body.properties)
        return {'count':len(results),'predictions':results}

    @router.get('/analytics/market', dependencies=auth, tags=['Analytics'])
    def market():
        return service.market()
    return router
