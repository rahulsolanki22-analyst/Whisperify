from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import async_engine, Base
from app.routes.lyrics import router as lyrics_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("whisperify.main")

# Modern lifespan context manager for FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown lifecycles.
    Automatically creates SQLite database tables if they don't exist yet.
    """
    logger.info("Initializing database and starting Whisperify Backend Services...")
    async with async_engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized successfully.")
    yield
    logger.info("Shutting down Whisperify Backend Services...")

app = FastAPI(
    title="Whisperify Backend API",
    description="Asynchronous backend boilerplate for Spotify Web Player fallback lyric provider utilizing AI Whisper transcriptions.",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS Middleware
# Chrome extensions run from 'chrome-extension://<extension-id>'. 
# Standard CORS allows wildcard '*' or explicit extension origins for development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Set explicit extension IDs in production (e.g. chrome-extension://...)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register endpoints routers
app.include_router(lyrics_router)

@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint to verify backend status.
    """
    return {
        "status": "online",
        "service": "whisperify-backend",
        "database": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    # Local dev runner helper
    uvicorn.run("app.main:app", host="127.0.0.1", port=8080, reload=True)
