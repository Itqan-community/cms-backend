from apps.publishers.models import Publisher


class PublisherRepository:
    def create(self, **kwargs: object) -> Publisher:
        return Publisher.objects.create(**kwargs)

    def slug_exists(self, slug: str) -> bool:
        return Publisher.objects.filter(slug=slug).exists()
