import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    FIREFLIES_API_KEY = os.getenv("FIREFLIES_API_KEY")
    MONGODB_URI = os.getenv("MONGODB_URI")
    SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
    
    # LLM Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    @classmethod
    def validate(cls):
        required = [] # Add required keys here based on deployment
        # for key in required:
        #     if not getattr(cls, key):
        #         raise ValueError(f"Missing configuration: {key}")
        pass

settings = Config()
