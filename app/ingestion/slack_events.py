from fastapi import APIRouter, Request, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging
import hmac
import hashlib
import time
import os
import requests
from app.config import settings
from app.services.storage import db

router = APIRouter()
logger = logging.getLogger(__name__)

# Request Models
class SlackEvent(BaseModel):
    type: str
    user: Optional[str] = None
    text: Optional[str] = None
    channel: Optional[str] = None
    ts: Optional[str] = None
    subtype: Optional[str] = None

class SlackPayload(BaseModel):
    token: Optional[str] = None
    challenge: Optional[str] = None
    type: str
    event: Optional[SlackEvent] = None
    event_id: Optional[str] = None
    event_time: Optional[int] = None

async def verify_slack_signature(request: Request, body: bytes):
    """
    Verifies the X-Slack-Signature header using the signing secret.
    """
    if not settings.SLACK_SIGNING_SECRET:
        logger.warning("⚠️ SLACK_SIGNING_SECRET not set. Skipping verification (UNSAFE).")
        return

    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not signature:
        raise HTTPException(status_code=400, detail="Missing Slack headers")

    # Prevent replay attacks (5 minutes)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Request too old")

    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    my_signature = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(my_signature, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

def reply_to_slack(channel: str, user_id: str, text: str):
    """
    Sends a message back to Slack using the Web API.
    """
    if not settings.SLACK_BOT_TOKEN:
        logger.error("❌ SLACK_BOT_TOKEN not set. Cannot reply.")
        return

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
        "Content-Type": "application/json"
    }
    # Ephemeral or visible? User didn't specify, defaulting to visible reply.
    payload = {
        "channel": channel,
        "text": text,
        # "user": user_id # If we wanted ephemeral
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        res.raise_for_status()
        data = res.json()
        if not data.get("ok"):
             logger.error(f"❌ Slack API Error: {data.get('error')}")
    except Exception as e:
        logger.error(f"❌ Failed to reply to Slack: {e}")

async def process_refinement_event(event: SlackEvent):
    """
    Background logic: Log, Store, Reply.
    """
    try:
        # 1. Filter
        if event.subtype == "bot_message":
            return
            
        logger.info(f"📨 Processing Slack Event: {event.type} from {event.user}")

        # 2. Store in MongoDB
        doc = {
            "slack_user_id": event.user,
            "channel_id": event.channel,
            "text": event.text,
            "timestamp": event.ts,
            "related_meeting_id": None, # Future: inference logic
            "processed": False
        }
        await db.save_refinement_request(doc)
        logger.info("💾 Refinement request saved to DB.")

        # 3. Reply
        reply_text = f"Got it <@{event.user}>. I’ve received your changes request and will update the draft shortly."
        reply_to_slack(event.channel, event.user, reply_text)

    except Exception as e:
        logger.error(f"❌ Error processing slack event: {e}")

@router.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint for Slack Events API.
    """
    body_bytes = await request.body()
    
    # 1. Verify Signature
    await verify_slack_signature(request, body_bytes)
    
    # 2. Parse Payload
    try:
        # Re-parse body from bytes
        payload_data = await request.json()
        payload = SlackPayload(**payload_data)
    except Exception as e:
        logger.error(f"Malformed payload: {e}")
        # Slack retries on failure, so generally we should validly error 
        # but if it's malformed JSON, maybe 400.
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 3. URL Verification (Challenge)
    if payload.type == "url_verification":
        logger.info("🔗 Handling Slack URL Verification")
        return {"challenge": payload.challenge}

    # 4. Event Callback
    if payload.type == "event_callback" and payload.event:
        event = payload.event
        # Supported events only
        if event.type in ["app_mention", "message"]:
            # Note: 'message' event includes 'message.im' if subscribed
            background_tasks.add_task(process_refinement_event, event)
        else:
            logger.info(f"Ignoring unsupported event type: {event.type}")
            
    return {"status": "ok"}
