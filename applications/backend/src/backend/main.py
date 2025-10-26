import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.routers import generic, ha, omnibooker, plex
from backend.utils import minimal_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Jarvis API"}


@app.get("/schema")
async def schema() -> JSONResponse:
    return JSONResponse(content=minimal_schema(app.openapi()))


app.include_router(generic.router)
app.include_router(plex.router)
app.include_router(ha.router)
app.include_router(omnibooker.router)  # not ready yet
