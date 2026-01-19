from ninja import Schema


class OkSchema[T](Schema):
    """A simple schema to return a success message"""

    message: str
    data: T | None = None
