from ninja import Schema


class OkSchema(Schema):
    """A simple schema to return a success message"""

    message: str
