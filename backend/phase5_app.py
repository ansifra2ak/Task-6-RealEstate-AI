"""Phase 5 app factory: Phase 1 entrypoints remain unchanged."""
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from backend.api.phase5 import make_router
from backend.services.phase5 import ROOT


def create_app(service, api_key, root=ROOT):
    if not isinstance(api_key,str) or len(api_key)<24:
        raise ValueError('Use an API key of at least 24 characters')
    app = FastAPI(title='RealEstate AI — Prediction & Intelligence API', version='0.5.0',
                  description='Registry-backed real estate estimates and training-only sample analytics. Local demonstration. Price and area units are unspecified in the source. Use Authorize to supply the X-API-Key.')

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError):
        # Do not echo supplied inputs, credentials, or raw request content.
        return JSONResponse(status_code=422, content={'detail':[{'loc':list(e['loc']),'msg':e['msg'],'type':e['type']} for e in exc.errors()]})

    app.include_router(make_router(service,api_key,root))
    return app
