from typing import TypedDict


class PublisherStats(TypedDict):
    total_publishers: int
    active_publishers: int
    verified_publishers: int
    total_countries: int
    last_updated: str
