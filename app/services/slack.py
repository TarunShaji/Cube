import requests
import logging
from app.config import settings
from app.state import MeetingState

logger = logging.getLogger(__name__)

class SlackService:
    def __init__(self):
        self.webhook_url = settings.SLACK_WEBHOOK_URL

    def send_notification(self, state: MeetingState):
        if not self.webhook_url:
            logger.warning("⚠️ Slack Webhook URL not set. Skipping notification.")
            return

        # 1. Header
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

        # 2. Executive Summary (from Email body usually, or generated)
        # We'll use the goal and summary context for now if email body is too long for a preview.
        # But actually, the user wants the "output". The email body is a good candidate, 
        # but let's stick to structured data for Slack for better readability.
        
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Goal:* {state.intent_context.primary_goal or 'No clear goal identified.'}"
            }
        })

        # 3. Decisions
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

        # 4. Action Items
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

        if state.email.body:
             blocks.append({"type": "divider"})
             blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn", 
                    "text": f"*Draft Email (Subject: {state.email.subject or 'No Subject'})*\n```{state.email.body}```"
                }
            })

        # 5. Footer / Link
        # If we had a dashboard, we'd link it here. For now, just a divider.
        blocks.append({"type": "divider"})
        
        payload = {"blocks": blocks}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info(f"✅ Slack notification sent for {state.meeting_id}")
        except Exception as e:
            logger.error(f"❌ Failed to send Slack notification: {e}")

slack_service = SlackService()
