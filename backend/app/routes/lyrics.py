from datetime import datetime
import json
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models import CachedLyrics
from app.schemas import TrackInfoRequest, LyricsResponse, TimestampLine
from app.services.lyrics_service import lyrics_service
from app.services.ai_service import ai_service
from app.services.translation_service import translation_service

router = APIRouter(prefix="/api/v1/lyrics", tags=["lyrics"])

@router.post("", response_model=LyricsResponse)
async def get_lyrics(request: TrackInfoRequest, db: AsyncSession = Depends(get_db)):
    """
    Core Fallback Lyric Retrieval Endpoint.
    
    1. Check Local DB Cache.
    2. Check External API (LRCLIB).
    3. If not found, return 404 with a specific message indicating AI Transcription is needed.
    """
    artist = request.artist.strip()
    song_title = request.song_title.strip()

    # Tier 1: Check SQLite Cache (case-insensitive query)
    stmt = select(CachedLyrics).where(
        func.lower(CachedLyrics.artist) == artist.lower(),
        func.lower(CachedLyrics.song_title) == song_title.lower()
    )
    result = await db.execute(stmt)
    cached_entry = result.scalar_one_or_none()

    if cached_entry:
        # Check if the cached entry is empty/instrumental but we now got scraped lyrics
        if (not cached_entry.lyrics_text or cached_entry.lyrics_text.strip() == "") and request.scraped_lyrics_text:
            lyrics_text = request.scraped_lyrics_text.strip()
            r_text, r_ts, t_text, t_ts = await translation_service.translate_and_transliterate(
                lyrics_text, None
            )
            cached_entry.lyrics_text = lyrics_text
            cached_entry.romanized_text = r_text
            cached_entry.romanized_timestamps = r_ts
            cached_entry.translated_text = t_text
            cached_entry.translated_timestamps = t_ts
            cached_entry.source = "spotify-scrape"
            await db.commit()
            await db.refresh(cached_entry)

        # Check if translation is needed but not yet cached
        needs_translation = False
        if not cached_entry.romanized_text and not cached_entry.translated_text:
            text_to_check = cached_entry.lyrics_text or ""
            if not text_to_check and cached_entry.timestamps:
                text_to_check = "\n".join([t.get("text", "") for t in cached_entry.timestamps])
            
            if translation_service.needs_transliteration_or_translation(text_to_check):
                needs_translation = True

        if needs_translation:
            r_text, r_ts, t_text, t_ts = await translation_service.translate_and_transliterate(
                cached_entry.lyrics_text, cached_entry.timestamps
            )
            if r_text or t_text:
                cached_entry.romanized_text = r_text
                cached_entry.romanized_timestamps = r_ts
                cached_entry.translated_text = t_text
                cached_entry.translated_timestamps = t_ts
                await db.commit()
                await db.refresh(cached_entry)

        # Convert timestamp JSON back to TimestampLine objects
        timestamps_list = None
        if cached_entry.timestamps:
            timestamps_list = [TimestampLine(**line) for line in cached_entry.timestamps]
            
        romanized_list = None
        if cached_entry.romanized_timestamps:
            romanized_list = [TimestampLine(**line) for line in cached_entry.romanized_timestamps]
            
        translated_list = None
        if cached_entry.translated_timestamps:
            translated_list = [TimestampLine(**line) for line in cached_entry.translated_timestamps]
            
        return LyricsResponse(
            artist=cached_entry.artist,
            song_title=cached_entry.song_title,
            lyrics_text=cached_entry.lyrics_text,
            timestamps=timestamps_list,
            romanized_text=cached_entry.romanized_text,
            romanized_timestamps=romanized_list,
            translated_text=cached_entry.translated_text,
            translated_timestamps=translated_list,
            source=cached_entry.source,
            is_cached=True,
            created_at=cached_entry.created_at
        )

    # Tier 2: Check External Lyric DB (LRCLIB)
    lyrics_text, timestamps, source = await lyrics_service.fetch_external_lyrics(artist, song_title)
    
    if lyrics_text or timestamps:
        # Translate if needed
        r_text, r_ts, t_text, t_ts = await translation_service.translate_and_transliterate(
            lyrics_text, timestamps
        )
        
        # Save to database cache
        new_cache = CachedLyrics(
            artist=artist,
            song_title=song_title,
            lyrics_text=lyrics_text,
            timestamps=timestamps,
            romanized_text=r_text,
            romanized_timestamps=r_ts,
            translated_text=t_text,
            translated_timestamps=t_ts,
            source=source
        )
        db.add(new_cache)
        await db.commit()
        await db.refresh(new_cache)

        return LyricsResponse(
            artist=artist,
            song_title=song_title,
            lyrics_text=lyrics_text,
            timestamps=[TimestampLine(**line) for line in timestamps] if timestamps else None,
            romanized_text=r_text,
            romanized_timestamps=[TimestampLine(**line) for line in r_ts] if r_ts else None,
            translated_text=t_text,
            translated_timestamps=[TimestampLine(**line) for line in t_ts] if t_ts else None,
            source=source,
            is_cached=False,
            created_at=new_cache.created_at
        )

    if request.scraped_lyrics_text:
        # Tier 2.5: Use scraped lyrics from client if provided
        lyrics_text = request.scraped_lyrics_text.strip()
        source = "spotify-scrape"
        
        # Translate if needed
        r_text, r_ts, t_text, t_ts = await translation_service.translate_and_transliterate(
            lyrics_text, None
        )
        
        # Save to database cache
        new_cache = CachedLyrics(
            artist=artist,
            song_title=song_title,
            lyrics_text=lyrics_text,
            timestamps=None,
            romanized_text=r_text,
            romanized_timestamps=r_ts,
            translated_text=t_text,
            translated_timestamps=t_ts,
            source=source
        )
        db.add(new_cache)
        await db.commit()
        await db.refresh(new_cache)

        return LyricsResponse(
            artist=artist,
            song_title=song_title,
            lyrics_text=lyrics_text,
            timestamps=None,
            romanized_text=r_text,
            romanized_timestamps=None,
            translated_text=t_text,
            translated_timestamps=None,
            source=source,
            is_cached=False,
            created_at=new_cache.created_at
        )

    # Tier 3 Trigger Indicator
    # If not found in DB or external APIs, throw 404 but provide key details so Chrome Extension knows to upload audio
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "message": "Lyrics not found in text databases.",
            "transcription_required": True,
            "artist": artist,
            "song_title": song_title
        }
    )

@router.post("/transcribe", response_model=LyricsResponse)
async def transcribe_song_audio(
    artist: str = Form(...),
    song_title: str = Form(...),
    provider: str = Form("groq"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Tier 3: Receive uploaded audio bytes (captured from Spotify web page or fetched),
    transcribe using Whisper APIs (OpenAI or Groq), cache the result, and return the synced lyrics.
    """
    artist = artist.strip()
    song_title = song_title.strip()

    # Read binary content from file
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty"
        )

    # Perform async transcription
    transcription_result = await ai_service.transcribe_audio(
        audio_bytes=audio_bytes,
        filename=file.filename or "audio.mp3",
        provider=provider
    )

    if not transcription_result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Transcription failed. Verify API keys and audio file format."
        )

    lyrics_text = transcription_result["lyrics_text"]
    timestamps = transcription_result["timestamps"]
    source = transcription_result["source"]

    # Translate if needed
    r_text, r_ts, t_text, t_ts = await translation_service.translate_and_transliterate(
        lyrics_text, timestamps
    )

    # Check if a cache entry was created in the meantime to prevent duplicates
    stmt = select(CachedLyrics).where(
        func.lower(CachedLyrics.artist) == artist.lower(),
        func.lower(CachedLyrics.song_title) == song_title.lower()
    )
    result = await db.execute(stmt)
    existing_entry = result.scalar_one_or_none()

    if existing_entry:
        # Update existing
        existing_entry.lyrics_text = lyrics_text
        existing_entry.timestamps = timestamps
        existing_entry.romanized_text = r_text
        existing_entry.romanized_timestamps = r_ts
        existing_entry.translated_text = t_text
        existing_entry.translated_timestamps = t_ts
        existing_entry.source = source
        existing_entry.created_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing_entry)
        saved_entry = existing_entry
    else:
        # Create new
        saved_entry = CachedLyrics(
            artist=artist,
            song_title=song_title,
            lyrics_text=lyrics_text,
            timestamps=timestamps,
            romanized_text=r_text,
            romanized_timestamps=r_ts,
            translated_text=t_text,
            translated_timestamps=t_ts,
            source=source
        )
        db.add(saved_entry)
        await db.commit()
        await db.refresh(saved_entry)

    return LyricsResponse(
        artist=artist,
        song_title=song_title,
        lyrics_text=lyrics_text,
        timestamps=[TimestampLine(**line) for line in timestamps] if timestamps else None,
        romanized_text=r_text,
        romanized_timestamps=[TimestampLine(**line) for line in r_ts] if r_ts else None,
        translated_text=t_text,
        translated_timestamps=[TimestampLine(**line) for line in t_ts] if t_ts else None,
        source=source,
        is_cached=False,
        created_at=saved_entry.created_at
    )
