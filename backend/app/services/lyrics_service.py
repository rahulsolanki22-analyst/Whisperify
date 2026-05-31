import logging
from typing import Any, Dict, Optional, Tuple
import httpx

logger = logging.getLogger("whisperify.lyrics_service")

class LyricsService:
    """
    Service layer handles querying external lyrics APIs (e.g., LRCLIB, Genius).
    """

    def __init__(self):
        # Initialize an async client. In production, consider managing this via app lifecycle events
        self.lrclib_base_url = "https://lrclib.net/api"

    async def fetch_from_lrclib(self, artist: str, track: str) -> Optional[Dict[str, Any]]:
        """
        Queries the free LRCLIB API to find synced or plain lyrics.
        Lrclib doesn't require authentication, making it an excellent primary external fallback.
        """
        url = f"{self.lrclib_base_url}/get"
        params = {
            "artist_name": artist,
            "track_name": track
        }
        
        headers = {
            "User-Agent": "WhisperifySpotifyExtension/1.0 (https://github.com/yourusername/whisperify)"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                logger.info(f"Querying LRCLIB for: {artist} - {track}")
                response = await client.get(url, params=params, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"LRCLIB match found for {artist} - {track}")
                    return data
                elif response.status_code == 404:
                    logger.info(f"LRCLIB returned 404 for {artist} - {track}")
                else:
                    logger.warning(f"LRCLIB returned status {response.status_code} for {artist} - {track}")
        except Exception as e:
            logger.error(f"Error querying LRCLIB: {str(e)}", exc_info=True)
        
        return None

    async def fetch_external_lyrics(self, artist: str, song_title: str) -> Tuple[Optional[str], Optional[list], str]:
        """
        Primary coordinator for tier-2 external lyrics database queries.
        Currently handles LRCLIB queries, returning (lyrics_text, timestamps, source_name).
        """
        lrclib_data = await self.fetch_from_lrclib(artist, song_title)
        
        if lrclib_data:
            # Extract plain lyrics text
            lyrics_text = lrclib_data.get("plainLyrics")
            if not lyrics_text and lrclib_data.get("syncedLyrics"):
                # Fallback if plainLyrics is empty but syncedLyrics exists
                lyrics_text = "\n".join([line.get("text", "") for line in lrclib_data.get("syncedLyrics", []) if isinstance(line, dict)])
            
            # Extract timestamps
            # LRCLIB provides raw synced lyrics in LRC format or syncedLyrics as a list of lines with time tags
            # Let's parse or format it into our TimestampLine schema format: [{"time": float, "text": str}]
            timestamps = []
            
            # If the response contains parsed synced lyrics directly, use them:
            # Note: lrclib.net '/get' API usually returns syncedLyrics as a string in LRC format.
            # We can include a basic helper parser for LRC text format: [mm:ss.xx] Lyric text
            raw_lrc = lrclib_data.get("syncedLyrics")
            if raw_lrc:
                timestamps = self._parse_lrc_string(raw_lrc)
            
            # If no synced lyrics but plain lyrics are found, return plain text
            if lyrics_text or timestamps:
                return lyrics_text, timestamps, "lrclib"

        # If genius API or other services are configured in the future, trigger them here
        # ...
        
        return None, None, "none"

    def _parse_lrc_string(self, lrc_text: str) -> list:
        """
        Parses raw LRC format lines (e.g. '[00:12.34] lyric text') into [{"time": seconds, "text": lyric}]
        """
        lines = lrc_text.splitlines()
        parsed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("["):
                continue
                
            try:
                # Find end of time bracket
                end_bracket = line.find("]")
                if end_bracket == -1:
                    continue
                    
                time_str = line[1:end_bracket]
                lyric_text = line[end_bracket+1:].strip()
                
                # Split minutes and seconds
                parts = time_str.split(":")
                if len(parts) == 2:
                    minutes = float(parts[0])
                    seconds = float(parts[1])
                    total_seconds = round(minutes * 60 + seconds, 2)
                    parsed_lines.append({
                        "time": total_seconds,
                        "text": lyric_text
                    })
            except Exception:
                # Skip invalid lines
                continue
                
        return parsed_lines

# Singleton instance for imports
lyrics_service = LyricsService()
