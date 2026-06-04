from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class TrackInfoRequest(BaseModel):
    """
    Schema for track details sent from the Chrome Extension when identifying a playing song.
    """
    artist: str = Field(..., description="The name of the artist", min_length=1)
    song_title: str = Field(..., description="The title of the song/track", min_length=1)
    duration_ms: Optional[int] = Field(None, description="The duration of the song in milliseconds")
    spotify_id: Optional[str] = Field(None, description="Optional Spotify track identifier")
    scraped_lyrics_text: Optional[str] = Field(None, description="Lyrics text scraped from the client DOM")

class TimestampLine(BaseModel):
    """
    Schema representing a single line of lyrics synced with a timestamp.
    """
    time: float = Field(..., description="Timestamp of the lyric line in seconds (relative to start of the track)")
    text: str = Field(..., description="The actual text content of the lyrics line")

class LyricsResponse(BaseModel):
    """
    Response schema returning found or transcribed lyrics back to the client.
    """
    artist: str
    song_title: str
    lyrics_text: Optional[str] = None
    timestamps: Optional[List[TimestampLine]] = None
    
    # Romanization & Translation fallbacks
    romanized_text: Optional[str] = None
    romanized_timestamps: Optional[List[TimestampLine]] = None
    translated_text: Optional[str] = None
    translated_timestamps: Optional[List[TimestampLine]] = None
    
    source: str = Field(..., description="The successful source (e.g., 'cache', 'lrclib', 'genius', 'whisper')")
    is_cached: bool = Field(..., description="True if retrieved from database cache, False otherwise")
    created_at: datetime

    class Config:
        from_attributes = True

class AudioTranscriptionResponse(BaseModel):
    """
    Schema indicating success status after submitting an audio track for AI transcription.
    """
    task_id: str = Field(..., description="Unique job or operation ID for the transcription task")
    status: str = Field(..., description="Current status of the transcription task (e.g., 'processing', 'completed', 'failed')")
    message: str = Field(..., description="Informative status message")
