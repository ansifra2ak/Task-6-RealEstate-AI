from fastapi import APIRouter
from backend.services.datasets import dataset_status

router = APIRouter(prefix='/api/v1')


@router.get('/health')
def health():
    return {'status': 'ok', 'version': '0.1.0', 'phase': 'foundation', 'model_ready': False}


@router.get('/datasets')
def datasets():
    return {'datasets': dataset_status()}
