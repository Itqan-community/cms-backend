import pytest

from apps.usage_tracking.models import TrafficChannel, TrafficKind, TrafficPlatform, TrafficStatusClass
from apps.usage_tracking.services.traffic_classify import (
    channel_for,
    is_bot_user_agent,
    platform_for,
    status_class_for,
    ua_family,
)

DALVIK = "Dalvik/2.1.0 (Linux; U; Android 14; SM-A156E Build/UP1A.231005.007)"
IOS = "AppleCoreMedia/1.0.0.21G93 (iPhone; U; CPU OS 17_6_1 like Mac OS X; en_us)"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"
JUST_AUDIO_ANDROID = "just_audio/2.0.7 (Linux;Android 14) ExoPlayerLib/2.18.7"
CUBOT = "Dalvik/2.1.0 (Linux; U; Android 13; Cubot P80 Build/TP1A.220624.014)"


class TestStatusClass:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (200, TrafficStatusClass.FULL),
            (206, TrafficStatusClass.PARTIAL),
            (204, TrafficStatusClass.SUCCESS),
            (304, TrafficStatusClass.REDIRECT),
            (404, TrafficStatusClass.CLIENT_ERROR),
            (503, TrafficStatusClass.SERVER_ERROR),
            (0, TrafficStatusClass.OTHER),
        ],
    )
    def test_status_class_for_where_status_given_should_map_to_class(self, status, expected):
        # Act / Assert
        assert status_class_for(status) == expected


class TestUaFamily:
    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            ("itqan-cli/0.4.0", "itqan-cli"),
            (DALVIK, "dalvik"),
            (IOS, "applecoremedia"),
            (JUST_AUDIO_ANDROID, "exoplayer"),
            ("just_audio/2.0.7 (iOS 17)", "just_audio"),
            ("curl/8.7.1", "curl"),
            ("python-requests/2.32.3", "python"),
            (CHROME, "browser"),
            ("", "empty"),
            ("SomethingElse/1.0", "other"),
        ],
    )
    def test_ua_family_where_user_agent_given_should_name_family(self, user_agent, expected):
        # Act / Assert
        assert ua_family(user_agent) == expected


class TestBots:
    @pytest.mark.parametrize(
        "user_agent",
        [
            "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)",
            "facebookexternalhit/1.1",
            "Mozilla/5.0 zgrab/0.x",
        ],
    )
    def test_is_bot_user_agent_where_crawler_should_be_true(self, user_agent):
        # Act / Assert
        assert is_bot_user_agent(user_agent) is True

    @pytest.mark.parametrize("user_agent", [DALVIK, CUBOT, IOS, CHROME, "itqan-cli/0.4.0"])
    def test_is_bot_user_agent_where_real_client_should_be_false(self, user_agent):
        # Act / Assert
        assert is_bot_user_agent(user_agent) is False


class TestPlatform:
    @pytest.mark.parametrize(
        ("user_agent", "expected"),
        [
            (DALVIK, TrafficPlatform.ANDROID),
            (JUST_AUDIO_ANDROID, TrafficPlatform.ANDROID),
            (IOS, TrafficPlatform.IOS),
            (CHROME, TrafficPlatform.WEB),
            ("itqan-cli/0.4.0", TrafficPlatform.DESKTOP),
            ("curl/8.7.1", TrafficPlatform.SERVER),
            ("SomethingElse/1.0", TrafficPlatform.UNKNOWN),
        ],
    )
    def test_platform_for_where_user_agent_given_should_map_platform(self, user_agent, expected):
        # Act / Assert
        assert platform_for(user_agent, ua_family(user_agent)) == expected


class TestChannel:
    @pytest.mark.parametrize(
        ("kind", "family", "has_install_id", "expected"),
        [
            (TrafficKind.GALLERY_DOWNLOAD, "browser", False, TrafficChannel.GALLERY),
            (TrafficKind.VERSION_FILE, "itqan-cli", False, TrafficChannel.CLI),
            (TrafficKind.VERSION_FILE, "python", True, TrafficChannel.CLI),
            (TrafficKind.AUDIO_SURAH, "browser", False, TrafficChannel.WEB),
            (TrafficKind.AUDIO_SURAH, "dalvik", False, TrafficChannel.APP_UNIDENTIFIED),
            (TrafficKind.API_CALL, "curl", False, TrafficChannel.SCRIPT),
            (TrafficKind.AUDIO_SURAH, "other", False, TrafficChannel.OTHER),
        ],
    )
    def test_channel_for_where_inputs_given_should_pick_first_matching_channel(
        self, kind, family, has_install_id, expected
    ):
        # Act / Assert
        assert channel_for(kind, family, has_install_id=has_install_id) == expected
