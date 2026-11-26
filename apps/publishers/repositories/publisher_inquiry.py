from django.utils import timezone

from apps.publishers.models import PublisherInquiry


class PublisherInquiryRepository:
    def create(self, **fields: str) -> PublisherInquiry:
        return PublisherInquiry.objects.create(**fields)

    def get(self, inquiry_id: int) -> PublisherInquiry | None:
        return PublisherInquiry.objects.filter(id=inquiry_id).first()

    def mark_emailed(self, inquiry: PublisherInquiry) -> None:
        inquiry.emailed_at = timezone.now()
        inquiry.save(update_fields=["emailed_at", "updated_at"])
