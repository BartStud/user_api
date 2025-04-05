from contextlib import asynccontextmanager

from app.minio import init_minio_bucket
from app.routers import users
from app.routers import specializations
from app.routers import socials
from app.routers import metrics
from app.es.index import init_indices
from app.es.instance import get_es_instance
from app.es.utils import wait_for_elasticsearch
from fastapi import FastAPI, Response

from app.routers import services
from app.routers import pets


es = get_es_instance()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not await wait_for_elasticsearch(es):
        raise Exception("Elasticsearch is not available after waiting")

    await init_indices(es)

    init_minio_bucket()

    yield


app = FastAPI(lifespan=lifespan)

app.include_router(users.router)
app.include_router(specializations.router)
app.include_router(metrics.router)
app.include_router(socials.router)
app.include_router(services.router)
app.include_router(pets.router)
