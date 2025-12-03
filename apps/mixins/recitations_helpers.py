import re


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


def extract_surah_number_from_filename(filename: str) -> int:
    """
    Example conventions:
    - '001.mp3'
    - '001-al-fatiha.mp3'
    - '1-al-fatiha.mp3'
    """
    m = re.match(r"(\d{1,3})", filename)
    if not m:
        raise ValueError(f"Cannot extract surah number from '{filename}'")
    return int(m.group(1))
