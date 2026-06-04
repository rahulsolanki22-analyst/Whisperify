import logging
from typing import Any, Dict, List, Optional, Tuple
import httpx

logger = logging.getLogger("whisperify.translation_service")

class TranslationService:
    """
    Service layer to perform free, keyless translation and romanization (transliteration) 
    using Google's public translate endpoint.
    """

    def __init__(self):
        self.translate_url = "https://translate.googleapis.com/translate_a/single"

    def needs_transliteration_or_translation(self, text: str) -> bool:
        """
        Determines if a text block contains non-Latin characters (e.g. Gurmukhi, Devanagari, Cyrillic)
        or non-English alphabets that benefit from transliteration and translation.
        """
        if not text:
            return False
        
        # Check if there are characters outside the basic Latin block (U+0000 to U+024F)
        for char in text:
            code = ord(char)
            # 0x024F is the end of Latin Extended-B. Characters above this are non-Latin scripts (e.g. Gurmukhi is 0x0A00)
            if code > 0x024F and char.isalpha():
                return True
        return False

    async def translate_and_transliterate(
        self, 
        lyrics_text: Optional[str], 
        timestamps: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Translates foreign lyrics to English AND romanizes (transliterates) the original script to Latin.
        Returns:
            (romanized_text, romanized_timestamps, translated_text, translated_timestamps)
        """
        if not lyrics_text and not timestamps:
            return None, None, None, None

        # 1. Prepare raw text to translate
        # To preserve line mappings, we join lines with a newline (\n) character
        lines = []
        if timestamps:
            lines = [line.get("text", "").strip() for line in timestamps]
        elif lyrics_text:
            lines = [line.strip() for line in lyrics_text.splitlines()]

        input_text = "\n".join(lines)
        if not input_text.strip():
            return None, None, None, None

        # Check if we actually need to translate/romanize
        if not self.needs_transliteration_or_translation(input_text):
            logger.info("Lyrics contain only Latin characters. Skipping translation.")
            return None, None, None, None

        logger.info(f"Initiating keyless Google Translation for {len(lines)} lines...")

        # 2. Call Google Translate Free Web API
        # dt=t returns translation, dt=rm returns romanization (transliteration)
        params_list = [
            ("client", "gtx"),
            ("sl", "auto"),
            ("tl", "en"),
            ("dt", "t"),
            ("dt", "rm")
        ]
        data = {
            "q": input_text
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.translate_url, params=params_list, data=data, headers=headers)
                
                if response.status_code != 200:
                    logger.error(f"Google Translate API returned status {response.status_code}: {response.text}")
                    return None, None, None, None
                
                result = response.json()
                return self._parse_google_response(result, lines, timestamps)
                
        except Exception as e:
            logger.error(f"Error calling Google Translate API: {str(e)}", exc_info=True)
            return None, None, None, None

    def _parse_google_response(
        self, 
        result: List[Any], 
        original_lines: List[str],
        original_timestamps: Optional[List[Dict[str, Any]]]
    ) -> Tuple[Optional[str], Optional[List[Dict[str, Any]]], Optional[str], Optional[List[Dict[str, Any]]]]:
        """
        Parses Google Translate arrays into lists of translated and romanized (transliterated) lines.
        """
        translated_segments = []
        romanized_lines = []

        # Google's format: result[0] contains translation/transliteration chunks
        if not result or not result[0]:
            return None, None, None, None

        chunks = result[0]
        
        # 1. Extract translated sentences
        for chunk in chunks:
            if len(chunk) >= 2 and isinstance(chunk[0], str) and chunk[0]:
                translated_segments.append(chunk[0])

            # Sometimes transliteration of the segment is at index 3
            if len(chunk) >= 4 and isinstance(chunk[3], str) and chunk[3]:
                # Split segments by newlines if they aggregated
                romanized_lines.extend(chunk[3].strip().splitlines())

        # Combine translations and split back into lines
        full_translation = "".join(translated_segments)
        translated_lines = [line.strip() for line in full_translation.splitlines()]

        # 2. Check for trailing transliteration array fallback
        # If romanized_lines is empty, Google puts the full transliteration in a trailing array:
        # e.g., [null, null, "romanized text..."] or ["", "", "romanized text..."]
        if not romanized_lines:
            for chunk in chunks:
                if len(chunk) >= 3 and (chunk[0] is None or chunk[0] == ""):
                    for idx in [2, 3]:
                        if idx < len(chunk) and isinstance(chunk[idx], str) and chunk[idx].strip():
                            romanized_lines = [line.strip() for line in chunk[idx].splitlines()]
                            break
                    if romanized_lines:
                        break

        # Cleanup: Ensure line counts align. If not, pad or trim to original line count.
        target_count = len(original_lines)
        
        # Adjust translated lines count
        if len(translated_lines) < target_count:
            translated_lines.extend([""] * (target_count - len(translated_lines)))
        elif len(translated_lines) > target_count:
            translated_lines = translated_lines[:target_count]

        # Adjust romanized lines count
        if len(romanized_lines) < target_count:
            romanized_lines.extend([""] * (target_count - len(romanized_lines)))
        elif len(romanized_lines) > target_count:
            romanized_lines = romanized_lines[:target_count]

        # 3. Re-assemble final outputs
        romanized_text = "\n".join(romanized_lines)
        translated_text = "\n".join(translated_lines)

        # Assemble synced timestamp structures if original timestamps exist
        romanized_timestamps = None
        translated_timestamps = None

        if original_timestamps:
            romanized_timestamps = []
            translated_timestamps = []
            for i, ts in enumerate(original_timestamps):
                # Copy timeline and substitute text
                romanized_timestamps.append({
                    "time": ts["time"],
                    "text": romanized_lines[i] if romanized_lines[i] else ts["text"]
                })
                translated_timestamps.append({
                    "time": ts["time"],
                    "text": translated_lines[i] if translated_lines[i] else ts["text"]
                })

        logger.info(f"Google Translation parsing complete. Mapped {target_count} lines successfully.")
        return romanized_text, romanized_timestamps, translated_text, translated_timestamps

# Singleton instance
translation_service = TranslationService()
