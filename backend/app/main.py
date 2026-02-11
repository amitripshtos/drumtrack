import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import jobs, upload

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DrumTrack API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(upload.router)
app.include_router(jobs.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
