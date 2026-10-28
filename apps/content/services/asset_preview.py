"""What the gallery plays or renders for assets without a text preview: a recitation's
first tracks, and a font's file with sample Quran text to set in it."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import PurePosixPath
import zipfile

from botocore.exceptions import BotoCoreError, ClientError
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.db.models.fields.files import FieldFile
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.content.models import Asset, AssetVersion, CategoryChoice, RecitationSurahTrack, StatusChoice
from apps.content.repositories.asset_preview import AssetPreviewRepository
from apps.core.ninja_utils.errors import ItqanError
from apps.core.utils.media_urls import public_media_url
from apps.quran.models import Ayah

logger = logging.getLogger(__name__)

PREVIEW_TRACKS = 3
# The sura whose ayahs a font preview is set in: Al-Fatiha.
SAMPLE_SURA = 1

# CSS @font-face format per extension, in the order a zip's members are preferred.
FONT_FORMATS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}
# A font inside a zip larger than this is not extracted (a font is well under 10 MB).
MAX_FONT_BYTES = 20 * 1024 * 1024
# The extracted file never changes for a given upload: its name can be cached long.
_FONT_NAME_CACHE_TTL = 30 * 24 * 60 * 60
_FONT_PREVIEW_DIR = "previews/fonts"


@dataclass(frozen=True)
class FontPreview:
    url: str
    file_name: str
    format: str
    sample: list[Ayah]


class AssetPreviewService:
    def __init__(self, repo: AssetPreviewRepository | None = None) -> None:
        self.repo = repo or AssetPreviewRepository()

    @staticmethod
    def _file_url(asset: Asset, file: FieldFile, request: HttpRequest) -> str:
        """CDN URL for open assets; the signed, expiring link for restricted ones."""
        return public_media_url(file, request) if asset.is_open_access else file.url

    def recitation_tracks(self, asset: Asset, request: HttpRequest) -> list[tuple[RecitationSurahTrack, str]]:
        """The first ``PREVIEW_TRACKS`` tracks of a READY recitation, with playable URLs.

        No access grant is needed: a few surahs are a sample, like the text previews.
        """
        tracks = []
        if asset.category == CategoryChoice.RECITATION and asset.status == StatusChoice.READY:
            tracks = self.repo.first_default_tracks(asset, PREVIEW_TRACKS)
        if not tracks:
            raise ItqanError(
                error_name="recitation_preview_unavailable",
                message=_("This recitation has no tracks to preview."),
                status_code=404,
            )
        return [(track, self._file_url(asset, track.audio_file, request)) for track in tracks]

    def font(self, asset: Asset, language: str | None, request: HttpRequest) -> FontPreview:
        """The published version's font file (pulled out of a zip upload) and Al-Fatiha
        to render in it. No access grant is needed, as for the other previews."""
        unavailable = ItqanError(
            error_name="font_preview_unavailable",
            message=_("This font has no file to preview in this language."),
            status_code=404,
        )
        if asset.category != CategoryChoice.FONT or asset.status != StatusChoice.READY:
            raise unavailable
        rendition = self.repo.consumer_rendition(asset, language or asset.language)
        version = rendition.published_version if rendition else None
        if version is None or not version.file_url:
            raise unavailable

        name = version.file_url.name
        if PurePosixPath(name).suffix.lower() not in FONT_FORMATS:
            name = self._extracted_font(version)
            if name is None:
                raise unavailable
        file = FieldFile(version, AssetVersion._meta.get_field("file_url"), name)
        file_name = PurePosixPath(name).name
        return FontPreview(
            url=self._file_url(asset, file, request),
            file_name=file_name,
            format=FONT_FORMATS[PurePosixPath(file_name).suffix.lower()],
            sample=self.repo.sura_ayahs(SAMPLE_SURA),
        )

    def _extracted_font(self, version: AssetVersion) -> str | None:
        """Storage name of the font pulled out of ``version``'s zip, extracting it on the
        first call. None when the upload holds no font (not a zip, or no font inside)."""
        digest = hashlib.sha256(version.file_url.name.encode()).hexdigest()[:12]
        directory = f"{_FONT_PREVIEW_DIR}/{version.pk}/{digest}"
        cache_key = f"content:font-preview:{version.pk}:{digest}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached or None

        storage = version.file_url.storage
        try:
            _, existing = storage.listdir(directory)
        except FileNotFoundError:
            existing = []
        if existing:
            name = f"{directory}/{existing[0]}"
        else:
            try:
                name = self._extract(version, directory)
            except (OSError, BotoCoreError, ClientError):
                # Storage unreachable: don't cache, the next request retries.
                logger.exception(f"Font preview extraction failed [version_id={version.pk}]")
                return None
        cache.set(cache_key, name or "", _FONT_NAME_CACHE_TTL)
        return name

    @staticmethod
    def _extract(version: AssetVersion, directory: str) -> str | None:
        storage = version.file_url.storage
        with storage.open(version.file_url.name, "rb") as upload:
            try:
                archive = zipfile.ZipFile(upload)
            except zipfile.BadZipFile:
                return None
            with archive:
                order = list(FONT_FORMATS)
                fonts = sorted(
                    (
                        member
                        for member in archive.infolist()
                        if not member.is_dir() and PurePosixPath(member.filename).suffix.lower() in FONT_FORMATS
                        # macOS archive metadata, not fonts.
                        and not member.filename.startswith("__MACOSX/")
                        and not PurePosixPath(member.filename).name.startswith("._")
                        and member.file_size <= MAX_FONT_BYTES
                    ),
                    key=lambda m: (order.index(PurePosixPath(m.filename).suffix.lower()), m.filename),
                )
                if not fonts:
                    return None
                font = fonts[0]
                content = archive.read(font)
        name = storage.save(f"{directory}/{PurePosixPath(font.filename).name}", ContentFile(content))
        logger.info(f"Font preview extracted [version_id={version.pk}, member={font.filename}]")
        return name
