# AWS EC2 Deployment Guide for Cube Intelligence

This document contains all information needed to deploy the Cube post-meeting automation system on AWS EC2.

---

## 📋 Project Summary

**Cube** is a FastAPI-based backend that:
- Receives webhooks from Fireflies.ai when meetings are transcribed
- Processes transcripts through an agentic LangGraph pipeline
- Sends draft emails to Slack for human review
- Allows iterative refinement via Slack DMs
- Opens Gmail with pre-filled drafts on approval

---

## 🔧 System Requirements

| Requirement | Minimum | Recommended |
|-------------|---------|-------------|
| Instance Type | t3.micro | t3.small or t3.medium |
| RAM | 1 GB | 2 GB |
| Storage | 8 GB EBS | 20 GB EBS |
| Python | 3.9+ | 3.11 |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

---

## 🔑 Required Environment Variables

Create a `.env` file with these keys:

```bash
# Fireflies.ai (GraphQL API for transcripts)
FIREFLIES_API_KEY=your_fireflies_api_key

# MongoDB (async driver via Motor)
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/cube?retryWrites=true&w=majority

# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/xxx
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SIGNING_SECRET=your_signing_secret

# LLM (Google Gemini)
GEMINI_API_KEY=your_gemini_api_key
```

### Where to Get These Keys:

| Key | Source |
|-----|--------|
| `FIREFLIES_API_KEY` | [Fireflies Dashboard](https://app.fireflies.ai/integrations) → API Key |
| `MONGODB_URI` | [MongoDB Atlas](https://cloud.mongodb.com) → Database → Connect → Drivers |
| `SLACK_WEBHOOK_URL` | [Slack API](https://api.slack.com/apps) → Your App → Incoming Webhooks |
| `SLACK_BOT_TOKEN` | Slack App → OAuth & Permissions → Bot User OAuth Token |
| `SLACK_SIGNING_SECRET` | Slack App → Basic Information → Signing Secret |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/app/apikey) |

---

## 📦 Python Dependencies

```
fastapi
uvicorn
python-dotenv
langchain
langgraph
langchain-anthropic
langchain-fireworks
langchain-google-genai
motor
pydantic
requests
```

---

## 🚀 Deployment Steps

### 1. Launch EC2 Instance

```bash
# Recommended: Ubuntu 22.04 LTS, t3.small
# Security Group: Allow inbound on ports 22 (SSH), 80, 443, 8000
```

### 2. Install System Dependencies

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip git nginx
```

### 3. Clone Repository

```bash
cd /home/ubuntu
git clone https://github.com/TarunShaji/Cube.git cube
cd cube
```

### 4. Create Virtual Environment

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 5. Configure Environment

```bash
# Create .env file with your keys
nano .env
# Paste your environment variables (see section above)
```

### 6. Test Locally

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
# Test: curl http://localhost:8000/health
```

---

## 🔄 Production Setup with systemd

### Create Service File

```bash
sudo nano /etc/systemd/system/cube.service
```

```ini
[Unit]
Description=Cube Intelligence API
After=network.target

[Service]
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/cube
Environment="PATH=/home/ubuntu/cube/venv/bin"
EnvironmentFile=/home/ubuntu/cube/.env
ExecStart=/home/ubuntu/cube/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Enable & Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable cube
sudo systemctl start cube
sudo systemctl status cube
```

---

## 🌐 Nginx Reverse Proxy (Optional but Recommended)

```bash
sudo nano /etc/nginx/sites-available/cube
```

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Or EC2 public IP

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/cube /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## 🔒 SSL with Certbot (For Custom Domain)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 🔗 Webhook Configuration

After deployment, update your **Fireflies webhook URL**:

1. Go to [Fireflies Integrations](https://app.fireflies.ai/integrations)
2. Find "Webhooks" or "Custom Integration"
3. Set the URL to: `https://your-domain.com/webhook/fireflies`

Update your **Slack App Event Subscriptions**:

1. Go to [Slack API](https://api.slack.com/apps) → Your App → Event Subscriptions
2. Set Request URL to: `https://your-domain.com/slack/events`
3. Subscribe to bot events: `message.im`, `app_mention`

Update **Slack Interactivity**:

1. Slack App → Interactivity & Shortcuts → Toggle ON
2. Set Request URL to: `https://your-domain.com/slack/interactions`

---

## 📊 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Health check |
| `/webhook/fireflies` | POST | Receives Fireflies webhooks |
| `/slack/events` | POST | Handles Slack events/DMs |
| `/slack/interactions` | POST | Handles button clicks |

---

## 🔍 Monitoring & Logs

```bash
# View live logs
sudo journalctl -u cube -f

# View last 100 lines
sudo journalctl -u cube -n 100

# Restart service
sudo systemctl restart cube
```

---

## 🛡️ Security Checklist

- [ ] EC2 Security Group: Only allow 22, 80, 443 inbound
- [ ] MongoDB Atlas: Whitelist EC2 IP or use `0.0.0.0/0` for dynamic IPs
- [ ] Use IAM roles instead of hardcoded AWS credentials (if using AWS services)
- [ ] Enable Slack request signature verification (already in codebase)
- [ ] Store `.env` securely, never commit to git
- [ ] Enable automatic security updates: `sudo apt install unattended-upgrades`

---

## 🔄 Updating the Application

```bash
cd /home/ubuntu/cube
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart cube
```

---

## 📋 Pre-Deployment Checklist

- [ ] MongoDB Atlas cluster created and URI ready
- [ ] Fireflies API key obtained
- [ ] Slack App created with Bot Token, Signing Secret, Webhook URL
- [ ] Google AI Studio API key for Gemini
- [ ] Domain name (optional, can use EC2 public IP)
- [ ] EC2 instance launched with Ubuntu 22.04
- [ ] Security Group configured (ports 22, 80, 443, 8000)

---

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError` | Ensure venv is activated and dependencies installed |
| MongoDB connection failed | Check MONGODB_URI and Atlas IP whitelist |
| Slack verification failed | Verify SLACK_SIGNING_SECRET matches app config |
| Webhook not received | Check EC2 Security Group allows inbound on port 8000/80 |
| 502 Bad Gateway (Nginx) | Check if uvicorn is running: `systemctl status cube` |

---

## 📞 Support

For issues specific to this deployment, check the logs first:
```bash
sudo journalctl -u cube -n 200 --no-pager
```
