"""
MongoDB connection manager for Medical AI Assistant.
Supports both local MongoDB and MongoDB Atlas (mongodb+srv://) via MONGODB_URL env variable.
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class MongoDB:
    """
    Singleton-style MongoDB connection manager.

    Usage:
        # On startup
        await MongoDB.connect(url="mongodb+srv://...")

        # Anywhere in the app
        db = MongoDB.get_db()
        await db["sessions"].find_one(...)

        # On shutdown
        await MongoDB.close()
    """

    _client: Optional[AsyncIOMotorClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    async def connect(
        cls,
        url: str,
        db_name: str = "medical_ai",
        *,
        server_selection_timeout_ms: int = 10_000,
        connect_timeout_ms: int = 10_000,
    ) -> AsyncIOMotorDatabase:
        """
        Initialize the Motor async client and verify connectivity via ping.

        Parameters
        ----------
        url : str
            Full MongoDB connection string. Supports both standard
            ``mongodb://`` and Atlas ``mongodb+srv://`` schemes.
        db_name : str
            Fallback database name if the URI does not contain one.
        server_selection_timeout_ms : int
            Max wait time (ms) for the driver to find a suitable server.
        connect_timeout_ms : int
            Max wait time (ms) to establish a TCP connection.

        Returns
        -------
        AsyncIOMotorDatabase
            The database instance ready for queries.
        """
        if cls._client is not None:
            logger.warning("MongoDB client already connected – reusing existing connection.")
            return cls._db

        logger.info("Connecting to MongoDB...")
        logger.info(f"  URI scheme: {'Atlas (SRV)' if url.startswith('mongodb+srv') else 'Standard'}")

        cls._client = AsyncIOMotorClient(
            url,
            serverSelectionTimeoutMS=server_selection_timeout_ms,
            connectTimeoutMS=connect_timeout_ms,
            retryWrites=True,
            w="majority",
        )

        cls._db = cls._client.get_default_database(default=db_name)

        await cls._client.admin.command("ping")
        logger.info(f"  ✅ Connected to MongoDB — database: {cls._db.name}")

        return cls._db

    @classmethod
    def get_db(cls) -> AsyncIOMotorDatabase:
        """
        Return the active database handle.

        Raises
        ------
        RuntimeError
            If called before ``connect()`` has been awaited.
        """
        if cls._db is None:
            raise RuntimeError(
                "MongoDB is not connected. Call `await MongoDB.connect(...)` first."
            )
        return cls._db

    @classmethod
    async def close(cls) -> None:
        """Gracefully close the MongoDB connection."""
        if cls._client is not None:
            cls._client.close()
            logger.info("  🔒 MongoDB connection closed.")
            cls._client = None
            cls._db = None

    @classmethod
    def is_connected(cls) -> bool:
        """Check whether the client has been initialized."""
        return cls._client is not None


def get_db() -> AsyncIOMotorDatabase:
    """
    Module-level shortcut so other files can do::

        from database.mongo import get_db
        db = get_db()
    """
    return MongoDB.get_db()
