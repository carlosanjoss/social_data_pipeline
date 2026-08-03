from pymongo import MongoClient
from pymongo.database import Database

from config import settings, get_logger

logger = get_logger(__name__)

_client: MongoClient | None = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongo_uri,
            serverSelectionTimeoutMS=5_000,
            connectTimeoutMS=5_000,
            maxPoolSize=10,
        )
        logger.info("mongodb_connected", uri=settings.mongo_uri.split("@")[-1])
    return _client


def get_db() -> Database:
    return get_client()[settings.mongo_db]


def close_client() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
        logger.info("mongodb_disconnected")
