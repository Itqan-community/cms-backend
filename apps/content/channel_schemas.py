from typing import Literal

from ninja import Schema

from apps.core.ninja_utils.errors import NinjaErrorResponse


class ChannelConsumersExtra(Schema):
    approved_count: int
    pending_count: int
    channels: list[str]


# 409 returned by PUT/PATCH when turning a distribution channel off would affect developers
# holding a pending or approved access request and `confirm_channel_change` was not sent.
ChannelConflictResponse = NinjaErrorResponse[Literal["channel_has_active_consumers"], ChannelConsumersExtra]
