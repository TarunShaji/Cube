from fastapi import FastAPI
from app.ingestion.webhook import router as webhook_router
from app.config import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Post-Meeting Intelligence")

app.include_router(webhook_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
