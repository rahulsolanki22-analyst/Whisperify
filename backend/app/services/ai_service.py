import logging
import os
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger("whisperify.ai_service")

class AIService:
    """
    Service layer to process and transcribe audio using AI models (OpenAI Whisper or Groq Whisper API).
    """

    def __init__(self):
        # API Keys - configured via environment variables
        self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        
        # API Endpoint configurations
        self.openai_whisper_url = "https://api.openai.com/v1/audio/transcriptions"
        self.groq_whisper_url = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe_audio(
        self, 
        audio_bytes: bytes, 
        filename: str,
        provider: str = "groq"
    ) -> Optional[Dict[str, Any]]:
        """
        Coordinates transcribing raw audio bytes using the selected provider.
        Returns a dict containing:
            - "text": The overall transcribed lyrics
            - "segments": Timestamp segments in format [{"time": float, "text": str}]
        """
        logger.info(f"Initiating AI audio transcription using provider: {provider}")
        
        if provider.lower() == "openai":
            return await self._transcribe_openai(audio_bytes, filename)
        else:
            return await self._transcribe_groq(audio_bytes, filename)

    async def _transcribe_openai(self, audio_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
        """
        Sends audio data to the OpenAI Whisper API to transcribe.
        Requires response_format="verbose_json" to get segment-level timestamps.
        """
        if not self.openai_api_key:
            logger.warning("OpenAI API Key not configured. Skipping transcription.")
            return None

        headers = {
            "Authorization": f"Bearer {self.openai_api_key}"
        }
        
        # Construct multipart files and form parameters
        # response_format="verbose_json" returns individual segments with start/end timestamps
        files = {
            "file": (filename, audio_bytes, "audio/mpeg")
        }
        data = {
            "model": "whisper-1",
            "response_format": "verbose_json",
            "timestamp_granularities[]": "segment"  # request segment level timestamps
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.openai_whisper_url, 
                    headers=headers, 
                    files=files, 
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return self._process_whisper_response(result, "whisper-openai")
                else:
                    logger.error(f"OpenAI Whisper returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error calling OpenAI Whisper: {str(e)}", exc_info=True)
            
        return None

    async def _transcribe_groq(self, audio_bytes: bytes, filename: str) -> Optional[Dict[str, Any]]:
        """
        Sends audio data to the high-speed Groq Cloud Whisper API.
        Extremely cost-effective and low-latency alternative.
        """
        if not self.groq_api_key:
            logger.warning("Groq API Key not configured. Skipping transcription.")
            return None

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}"
        }
        
        files = {
            "file": (filename, audio_bytes, "audio/mpeg")
        }
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json"
        }

        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(
                    self.groq_whisper_url, 
                    headers=headers, 
                    files=files, 
                    data=data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return self._process_whisper_response(result, "whisper-groq")
                else:
                    logger.error(f"Groq Whisper returned status {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Error calling Groq Whisper: {str(e)}", exc_info=True)
            
        return None

    def _process_whisper_response(self, raw_result: Dict[str, Any], source_name: str) -> Dict[str, Any]:
        """
        Helper method to standardise output format from raw Whisper API verbose json models.
        """
        full_text = raw_result.get("text", "")
        raw_segments = raw_result.get("segments", [])
        
        formatted_segments = []
        for segment in raw_segments:
            formatted_segments.append({
                "time": float(segment.get("start", 0.0)),
                "text": segment.get("text", "").strip()
            })
            
        return {
            "lyrics_text": full_text,
            "timestamps": formatted_segments,
            "source": source_name
        }

# Singleton instance
ai_service = AIService()
