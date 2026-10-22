import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from faster_whisper import WhisperModel


load_dotenv()

# tiny / base / small / medium. For Arabic, "small" or "medium" is better.
# The model is loaded once, when the server starts.
model = WhisperModel(os.getenv("WHISPER_MODEL", "small"), device="cpu", compute_type="int8")


def transcribe_audio(audio_bytes, filename="audio.webm", language=None):
    """Convert speech to text with Faster-Whisper.

    language: "ar", "en" or None (None = detect the language automatically).
    Returns {"text": "...", "language": "ar"}
    """
    suffix = Path(filename or "audio.webm").suffix or ".webm"

    # Faster-Whisper reads from a file, so we save the audio in a temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(audio_bytes)
        temp_path = temp_file.name

    try:
        segments, info = model.transcribe(temp_path, language=language, beam_size=5, vad_filter=True)

        # "segments" is read one piece at a time, so we join the pieces
        text = " ".join(segment.text.strip() for segment in segments).strip()
    finally:
        os.remove(temp_path)

    return {"text": text, "language": info.language}