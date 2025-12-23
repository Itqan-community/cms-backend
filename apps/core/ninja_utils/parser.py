import json

from django.http import HttpRequest
from django.utils.datastructures import MultiValueDict
from ninja.parser import Parser
from ninja.types import DictStrAny


class NinjaParser(Parser):
    def parse_querydict(self, data: MultiValueDict, list_fields: list[str], request: HttpRequest) -> DictStrAny:
        """Parse the incoming query parameters.
        to avoid using json.loads because it can throw errors for semi-valid json i.e. single quoted strings
        """
        if isinstance(data, bytes | str):
            data = json.loads(data)
        return super().parse_querydict(data, list_fields, request)
