import asyncio
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import QdrantClient, models
from config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def reset_mongodb():
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client["medical_ai"]
    
    collections_to_reset = ["sessions", "users", "chat_feedbacks", "health_corners", "unsafe_logs"]
    
    for col_name in collections_to_reset:
        count_before = await db[col_name].count_documents({})
        logger.info(f"Collection '{col_name}': Found {count_before} documents before reset.")
        if count_before > 0:
            result = await db[col_name].delete_many({})
            logger.info(f"  -> Deleted {result.deleted_count} documents from '{col_name}'.")
        else:
            logger.info(f"  -> Collection '{col_name}' is already empty.")

def reset_qdrant():
    logger.info("Connecting to Qdrant Cloud...")
    params = settings.get_qdrant_client_params()
    client = QdrantClient(**params)
    
    collection_name = "chat_history"
    try:
        # Check if collection exists
        info = client.get_collection(collection_name)
        points_count = info.points_count
        logger.info(f"Qdrant Collection '{collection_name}': Found {points_count} points before reset.")
        if points_count > 0:
            client.delete(
                collection_name=collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter()
                )
            )
            logger.info(f"  -> Successfully deleted all points from Qdrant collection '{collection_name}'.")
        else:
            logger.info(f"  -> Qdrant collection '{collection_name}' is already empty.")
    except Exception as e:
        logger.warning(f"Could not reset Qdrant collection '{collection_name}': {e}")

async def main():
    logger.info("=== STARTING TEST DATA RESET PROCESS ===")
    await reset_mongodb()
    reset_qdrant()
    logger.info("=== TEST DATA RESET PROCESS COMPLETED ===")

if __name__ == "__main__":
    asyncio.run(main())
