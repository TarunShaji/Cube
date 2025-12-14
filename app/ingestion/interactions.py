"""
Slack Interactions Handler

Handles interactive component callbacks (buttons, etc.) from Slack.
"""

from fastapi import APIRouter, Request, HTTPException
import logging
import hmac
import hashlib
import time
import json
from app.config import settings
from app.services.storage import db

router = APIRouter()
logger = logging.getLogger(__name__)


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


def send_response_to_slack(response_url: str, text: str):
    """
    Sends a response back to Slack using the response_url.
    """
    import requests
    
    try:
        payload = {
            "response_type": "in_channel",
            "replace_original": False,
            "text": text
        }
        res = requests.post(response_url, json=payload, timeout=5)
        res.raise_for_status()
    except Exception as e:
        logger.error(f"❌ Failed to send response to Slack: {e}")


@router.post("/slack/interactions")
async def slack_interactions(request: Request):
    """
    Endpoint for Slack Interactive Components (buttons, modals, etc.).
    
    Slack sends interactions as application/x-www-form-urlencoded with a 'payload' field.
    """
    body_bytes = await request.body()
    
    # Verify signature
    await verify_slack_signature(request, body_bytes)
    
    # Parse form data
    form_data = await request.form()
    payload_str = form_data.get("payload")
    
    if not payload_str:
        raise HTTPException(status_code=400, detail="Missing payload")
    
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in payload")
    
    logger.info(f"📨 Received Slack interaction: type={payload.get('type')}")
    
    # Handle block_actions (button clicks)
    if payload.get("type") == "block_actions":
        actions = payload.get("actions", [])
        user = payload.get("user", {})
        response_url = payload.get("response_url")
        
        for action in actions:
            action_id = action.get("action_id")
            value = action.get("value")
            
            logger.info(f"   Action: {action_id}, Value: {value}, User: {user.get('username')}")
            
            if action_id in ("approve_draft", "approve_and_send"):
                # Approve the meeting
                meeting_id = value
                logger.info(f"✅ Approving meeting: {meeting_id}")
                
                # Get and update meeting
                meeting = await db.get_meeting(meeting_id)
                if meeting:
                    meeting.human_feedback.status = "approved"
                    meeting.human_feedback.slack_user_id = user.get("id")
                    await db.save_meeting(meeting)
                    logger.info(f"💾 Meeting {meeting_id} approved and saved")
                    
                    # Send confirmation
                    if response_url:
                        send_response_to_slack(
                            response_url,
                            f"✅ Draft approved by <@{user.get('id')}>! Ready for finalization."
                        )
                else:
                    logger.warning(f"⚠️ Meeting {meeting_id} not found")
                    if response_url:
                        send_response_to_slack(
                            response_url,
                            "⚠️ Meeting not found. It may have been already processed."
                        )
    
    # Slack requires a 200 response within 3 seconds
    return {"status": "ok"}
