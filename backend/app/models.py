from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import String, Text, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

class CachedLyrics(Base):
    """
    SQLAlchemy model representing cached lyrics for songs processed or fetched by the Whisperify engine.
    """
    __tablename__ = "cached_lyrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Store standard search parameters, indexed for fast lookups
    artist: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    song_title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    
    # Raw lyrics text (useful for fallback text displays)
    lyrics_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # JSON-structured lyrics timestamp data.
    # Expected format:
    # [
    #   {"time": 12.5, "text": "I hear the drums echoing tonight"},
    #   {"time": 18.2, "text": "But she hears only whispers of some quiet conversation"}
    # ]
    timestamps: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Keyless Transliteration (Romanized text and timestamps)
    romanized_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    romanized_timestamps: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Keyless Translation (English text and timestamps)
    translated_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    translated_timestamps: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Metadata tracking where the lyrics came from (e.g., 'native', 'lrclib', 'genius', 'whisper')
    source: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    
    # Time the entry was cached
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<CachedLyrics {self.artist} - {self.song_title} (Source: {self.source})>"
