from ninja import Schema

from apps.content.repositories.recitation import RecitationRepository
from apps.content.services.recitation import RecitationService
from apps.core.ninja_utils.request import Request
from apps.core.ninja_utils.router import ItqanRouter
from apps.core.ninja_utils.tags import NinjaTag

router = ItqanRouter(tags=[NinjaTag.RECITATIONS])


class RecitationStatisticsOut(Schema):
    total_recitations: int
    total_reciters: int
    total_riwayahs: int


@router.get("recitation-statistics/", response=RecitationStatisticsOut)
def get_recitation_statistics(request: Request):
    repo = RecitationRepository()
    service = RecitationService(repo)

    publisher_q = request.publisher_q("resource__publisher")
    publisher_id = request.publisher.id if request.publisher else None

    return service.get_recitation_statistics(publisher_q, publisher_id=publisher_id)
