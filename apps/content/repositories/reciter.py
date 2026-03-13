from apps.content.models import Reciter


class ReciterRepository:
    def create(self, **kwargs: object) -> Reciter:
        return Reciter.objects.create(**kwargs)

    def slug_exists(self, slug: str) -> bool:
        return Reciter.objects.filter(slug=slug).exists()
