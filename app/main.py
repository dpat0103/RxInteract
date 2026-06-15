import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.routers import drugs
from app.logger import get_logger
from app.scheduler import start_scheduler, stop_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="MedicationInteractor API",
    description="Check drug interactions and retrieve FDA label data via RxNorm and OpenFDA",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(drugs.router, prefix="/drugs", tags=["Drugs"])


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({duration}ms)")
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again."}
    )


@app.get("/")
async def root():
    return {"status": "ok", "message": "MedicationInteractor API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}