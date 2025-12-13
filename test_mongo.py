from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

mongo_uri = os.getenv("MONGODB_URI")
if not mongo_uri:
    raise RuntimeError("MONGODB_URI not found in .env")

client = MongoClient(mongo_uri)
db = client["cube"]

db.test.insert_one({"status": "mongo_connected"})
print("MongoDB connection successful")
