import re

from apps.core.ninja_utils.errors import ItqanError


def get_mp3_duration_ms(django_file) -> int:
    """
    Return duration (ms) for an MP3 Django File; returns 0 on error.
    """
    try:
        from mutagen.mp3 import MP3  # type: ignore[import-not-found]

        f = getattr(django_file, "file", django_file)
        try:
            f.seek(0)
        except Exception:
            pass
        audio = MP3(f)
        return int(audio.info.length * 1000)
    except Exception:
        return 0


def extract_surah_number_from_mp3_filename(filename: str) -> int:
    """
    Accept '001.mp3' OR 'anything_001.mp3'; take last 3 digits before extension.
    """
    m = re.search(r"(\d{3})\.mp3$", filename.strip(), flags=re.IGNORECASE)
    if not m:
        raise ItqanError("invalid_filename", f"Filename must end with surah number as 3 digits .mp3: {filename}")
    num = int(m.group(1))
    if not (1 <= num <= 114):
        raise ItqanError("invalid_surah_number", f"Surah number is out of range 1..114: {num}")
    return num
