from contextlib import asynccontextmanager
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from backend.core import telemetry, cache
from backend.api.router import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    telemetry.init_telemetry()
    await cache.init_cache()
    yield
    await cache.close_cache()
    telemetry.shutdown_telemetry()  # flush the last spans of any incident

app = FastAPI(title="DevGuard AI", lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)  # honors incoming traceparent automatically
app.include_router(router)
