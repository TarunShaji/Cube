from fastapi import FastAPI
from app.ingestion.webhook import router as webhook_router
from app.ingestion.slack_events import router as slack_events_router
from app.config import settings
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Cube Intelligence API")

# Include Routers
app.include_router(webhook_router)
app.include_router(slack_events_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
