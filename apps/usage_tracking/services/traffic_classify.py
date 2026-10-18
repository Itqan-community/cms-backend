"""Classifies requests by status, client family, platform, channel and bot traffic.

User agents are attacker-controlled; classification only ever labels a row, it never
decides access, so a spoofed user agent can at worst mislabel its own request.
"""

import re

from apps.usage_tracking.models import TrafficChannel, TrafficKind, TrafficPlatform, TrafficStatusClass

# Crawler conventions ("Name/1.0", "+http://..." contact URL) and known scanners. Deliberately
# not a bare "bot" match: Android phone models such as "Cubot P80" contain it.
_BOT_RE = re.compile(
    r"bot/\d|bot;|\+https?://|spider|crawler|facebookexternalhit|httrack|headlesschrome|"
    r"masscan|zgrab|nuclei|nikto|sqlmap|censys",
    re.IGNORECASE,
)

# Checked in order; the first match names the family.
_FAMILIES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("itqan-cli", re.compile(r"^itqan-cli/", re.IGNORECASE)),
    ("exoplayer", re.compile(r"ExoPlayer", re.IGNORECASE)),
    ("dalvik", re.compile(r"\bDalvik/")),
    ("just_audio", re.compile(r"just_audio", re.IGNORECASE)),
    ("okhttp", re.compile(r"\bokhttp/", re.IGNORECASE)),
    ("dart", re.compile(r"^Dart/")),
    ("applecoremedia", re.compile(r"AppleCoreMedia")),
    ("cfnetwork", re.compile(r"CFNetwork")),
    ("curl", re.compile(r"^curl/", re.IGNORECASE)),
    ("wget", re.compile(r"^Wget/", re.IGNORECASE)),
    ("python", re.compile(r"python-requests|python-urllib|aiohttp|httpx", re.IGNORECASE)),
    ("node", re.compile(r"^node|axios|undici|node-fetch", re.IGNORECASE)),
    ("go", re.compile(r"Go-http-client")),
    ("browser", re.compile(r"^Mozilla/")),
)
_APP_FAMILIES = frozenset({"exoplayer", "dalvik", "just_audio", "okhttp", "dart", "applecoremedia", "cfnetwork"})
_SCRIPT_FAMILIES = frozenset({"curl", "wget", "python", "node", "go", "empty"})
_ANDROID_RE = re.compile(r"Android", re.IGNORECASE)
_IOS_RE = re.compile(r"iPhone|iPad|iPod|\biOS\b|CPU OS", re.IGNORECASE)


def status_class_for(status: int) -> str:
    if status == 200:
        return TrafficStatusClass.FULL
    if status == 206:
        return TrafficStatusClass.PARTIAL
    if 200 <= status < 300:
        return TrafficStatusClass.SUCCESS
    if 300 <= status < 400:
        return TrafficStatusClass.REDIRECT
    if 400 <= status < 500:
        return TrafficStatusClass.CLIENT_ERROR
    if 500 <= status < 600:
        return TrafficStatusClass.SERVER_ERROR
    return TrafficStatusClass.OTHER


def ua_family(user_agent: str) -> str:
    if not user_agent.strip():
        return "empty"
    for family, pattern in _FAMILIES:
        if pattern.search(user_agent):
            return family
    return "other"


def is_bot_user_agent(user_agent: str) -> bool:
    return bool(_BOT_RE.search(user_agent))


def platform_for(user_agent: str, family: str) -> str:
    if family == "browser":
        return TrafficPlatform.WEB
    if family == "itqan-cli":
        return TrafficPlatform.DESKTOP
    if family in _SCRIPT_FAMILIES:
        return TrafficPlatform.SERVER
    if family in {"dalvik", "exoplayer", "okhttp"} or _ANDROID_RE.search(user_agent):
        return TrafficPlatform.ANDROID
    if family in {"applecoremedia", "cfnetwork"} or _IOS_RE.search(user_agent):
        return TrafficPlatform.IOS
    return TrafficPlatform.UNKNOWN


def channel_for(kind: str, family: str, *, has_install_id: bool) -> str:
    """First matching rule wins (spec §5.1). `app_identified` is added in plan 2."""
    if kind == TrafficKind.GALLERY_DOWNLOAD:
        return TrafficChannel.GALLERY
    if family == "itqan-cli" or has_install_id:
        return TrafficChannel.CLI
    if family == "browser":
        return TrafficChannel.WEB
    if family in _APP_FAMILIES:
        return TrafficChannel.APP_UNIDENTIFIED
    if family in _SCRIPT_FAMILIES:
        return TrafficChannel.SCRIPT
    return TrafficChannel.OTHER
