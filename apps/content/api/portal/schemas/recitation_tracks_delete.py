from ninja import Schema

from apps.core.ninja_utils.router import ItqanRouter

# Kept to satisfy broad portal router autodiscovery.
router = ItqanRouter()


class DeleteTracksIn(Schema):
    track_ids: list[int]
