from motor.motor_asyncio import AsyncIOMotorClient
from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple
from typing import Optional, Dict, Any, AsyncIterator, Sequence
from app.config import settings
import logging
import json
from pydantic import BaseModel

logger = logging.getLogger(__name__)

def _serialize_for_mongo(obj: Any) -> Any:
    """
    Recursively serialize objects to JSON-compatible types for MongoDB.
    Handles Pydantic models, dicts, lists, and other complex objects.
    """
    if isinstance(obj, BaseModel):
        # Pydantic model -> convert to dict
        return _serialize_for_mongo(obj.model_dump())
    elif isinstance(obj, dict):
        # Recursively serialize dict values
        return {k: _serialize_for_mongo(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        # Recursively serialize list/tuple items
        return [_serialize_for_mongo(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        # JSON-safe primitives
        return obj
    else:
        # For other objects, try to convert to string as fallback
        try:
            # Try JSON serialization as a test
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # Not JSON serializable, convert to string
            return str(obj)


class MongoDBCheckpointSaver(BaseCheckpointSaver):
    """
    Persistent checkpoint storage using MongoDB.
    Enables pipeline to pause, save state, and resume later.
    """
    
    def __init__(self):
        self.client = AsyncIOMotorClient(settings.MONGODB_URI)
        self.db = self.client.get_database("cube_intelligence")
        self.checkpoints = self.db.get_collection("checkpoints")
        logger.info("✅ MongoDB Checkpoint Saver initialized")
    
    async def aget_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Retrieve checkpoint tuple from MongoDB"""
        thread_id = config["configurable"]["thread_id"]
        logger.info(f"🔍 Loading checkpoint for thread: {thread_id}")
        
        doc = await self.checkpoints.find_one({"thread_id": thread_id})
        if not doc:
            logger.info(f"   No checkpoint found")
            return None
        
        logger.info(f"   ✅ Checkpoint loaded")
        
        # Return CheckpointTuple (LangGraph expects this format)
        return CheckpointTuple(
            config=config,
            checkpoint=doc.get("checkpoint"),
            metadata=doc.get("metadata", {}),
            parent_config=doc.get("parent_config")
        )
    
    async def aput(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Dict[str, Any],
        new_versions: Dict[str, Any]  # New parameter added in recent LangGraph versions
    ) -> Dict[str, Any]:
        """Save checkpoint to MongoDB"""
        thread_id = config["configurable"]["thread_id"]
        logger.info(f"💾 Saving checkpoint for thread: {thread_id}")
        
        # Serialize all data to JSON-compatible format for MongoDB
        serialized_checkpoint = _serialize_for_mongo(checkpoint)
        serialized_metadata = _serialize_for_mongo(metadata)
        serialized_config = _serialize_for_mongo(config)
        serialized_new_versions = _serialize_for_mongo(new_versions)
        
        await self.checkpoints.replace_one(
            {"thread_id": thread_id},
            {
                "thread_id": thread_id,
                "checkpoint": serialized_checkpoint,
                "metadata": serialized_metadata,
                "config": serialized_config,
                "parent_config": serialized_metadata.get("parent_config"),
                "saved_at": serialized_checkpoint.get("ts", None),
                "new_versions": serialized_new_versions
            },
            upsert=True
        )
        logger.info(f"   ✅ Checkpoint saved")
        return config
    
    async def aput_writes(self, config: Dict[str, Any], writes: Sequence[tuple], task_id: str) -> None:
        """Store intermediate writes (required by LangGraph but we can ignore for now)"""
        pass
    
    def get_tuple(self, config: Dict[str, Any]) -> Optional[CheckpointTuple]:
        """Sync version (not used in async context)"""
        raise NotImplementedError("Use aget_tuple for async context")
    
    def put(self, config: Dict[str, Any], checkpoint: Dict[str, Any], metadata: Dict[str, Any], new_versions: Dict[str, Any]) -> Dict[str, Any]:
        """Sync version (not used in async context)"""
        raise NotImplementedError("Use aput for async context")
    
    def put_writes(self, config: Dict[str, Any], writes: Sequence[tuple], task_id: str) -> None:
        """Sync version (not used in async context)"""
        raise NotImplementedError("Use aput_writes for async context")
    
    async def alist(self, config: Dict[str, Any]) -> AsyncIterator[CheckpointTuple]:
        """List all checkpoints for a thread (optional, not critical)"""
        thread_id = config["configurable"]["thread_id"]
        cursor = self.checkpoints.find({"thread_id": thread_id}).sort("saved_at", -1)
        
        async for doc in cursor:
            yield CheckpointTuple(
                config=doc.get("config", config),
                checkpoint=doc.get("checkpoint"),
                metadata=doc.get("metadata", {}),
                parent_config=doc.get("parent_config")
            )

