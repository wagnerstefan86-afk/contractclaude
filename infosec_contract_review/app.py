from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infosec_contract_review.api import packages, analysis, review, config

app = FastAPI(
    title="InfoSec Contract Review API",
    version="0.1.0-poc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(packages.router)
app.include_router(analysis.router)
app.include_router(review.router)
app.include_router(config.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0-poc"}
