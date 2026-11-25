from fastapi import FastAPI
from backend.api.system import router

app = FastAPI(title='RealEstate AI — Capstone', version='0.1.0',
              description='Phase 1 foundation. No prediction model is served yet.')
app.include_router(router)
