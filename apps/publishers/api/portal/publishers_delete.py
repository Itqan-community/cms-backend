from django.db.models import ProtectedError
from django.http import HttpResponse

from apps.core.ninja_utils.errors import ItqanError, NinjaErrorResponse
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag
from apps.publishers.models import Publisher

router = ItqanRouter(tags=[NinjaTag.PUBLISHERS])


@router.delete("publishers/{id}/", response={204: None, 404: NinjaErrorResponse, 409: NinjaErrorResponse})
def delete_publisher(request: Request, id: int):
    try:
        publisher = Publisher.objects.get(id=id)
    except Publisher.DoesNotExist as err:
        raise ItqanError("publisher_not_found", "Publisher not found", status_code=404) from err

    try:
        publisher.delete()
    except ProtectedError as err:
        raise ItqanError(
            "publisher_has_resources",
            "Publisher cannot be deleted while related resources exist",
            status_code=409,
        ) from err

    return HttpResponse(status=204)
