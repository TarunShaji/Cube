import requests
import logging
from app.config import settings
from app.state import MeetingState

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self):
        self.webhook_url = settings.SLACK_WEBHOOK_URL

    def send_notification(self, state: MeetingState, channel_id: str = None):
        """
        Sends the formatted meeting state to Slack.
        - If channel_id is provided, uses chat.postMessage (Bot Token).
        - If channel_id is MISSING, falls back to Webhook URL (Legacy/Default).
        """
        
        # Build Blocks (Common Logic)
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🧠 Cube Intelligence: {state.metadata.title or 'Untitled Meeting'}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Date:*\n{state.metadata.date}"},
                    {"type": "mrkdwn", "text": f"*Intent:*\n{state.intent_context.meeting_type or 'N/A'}"}
                ]
            },
            {"type": "divider"}
        ]

        # Executive Summary
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Goal:* {state.intent_context.primary_goal or 'No clear goal identified.'}"
            }
        })

        # Decisions
        all_decisions = []
        for t in state.topics:
            if t.decisions:
                all_decisions.extend(t.decisions)
        
        if all_decisions:
            decisions_text = "\n".join([f"• {d}" for d in all_decisions])
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Key Decisions:*\n{decisions_text}"}
            })

        # Action Items
        if state.commitments:
            tasks_text = ""
            for c in state.commitments:
                tasks_text += f"• *{c.owner}*: {c.task} (Due: {c.due})\n"
            
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Action Items:*\n{tasks_text}"}
            })
        else:
             blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": "*Action Items:*\n_No explicit commitments found._"}
            })

        # Email Draft
        if state.email.body:
             blocks.append({"type": "divider"})
             blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": f"*Draft Email (Subject: {state.email.subject or 'No Subject'})*\n```{state.email.body}```"
                }
            })

        blocks.append({"type": "divider"})
        
        # SENDING LOGIC
        try:
            # 1. Prefer Dynamic Channel (Bot Token)
            if channel_id and settings.SLACK_BOT_TOKEN:
                url = "https://slack.com/api/chat.postMessage"
                headers = {
                    "Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "channel": channel_id,
                    "blocks": blocks,
                    "text": f"New Intelligence for {state.metadata.title}" # Fallback text
                }
                response = requests.post(url, headers=headers, json=payload, timeout=10)
                response.raise_for_status()
                data = response.json()
                if not data.get("ok"):
                    logger.error(f"❌ Slack API Error (postMessage): {data.get('error')}")
                else:
                    logger.info(f"✅ Slack notification sent to channel {channel_id}")
                return

            # 2. Fallback to Webhook
            if self.webhook_url:
                payload = {"blocks": blocks}
                response = requests.post(self.webhook_url, json=payload, timeout=10)
                response.raise_for_status()
                logger.info(f"✅ Slack notification sent via Webhook")
            else:
                 logger.warning("⚠️ No Slack destination available (Missing Channel ID & Webhook URL)")

        except Exception as e:
            logger.error(f"❌ Failed to send Slack notification: {e}")

slack_service = SlackService()
