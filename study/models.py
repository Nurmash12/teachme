from django.db import models


class Source(models.Model):
    title = models.CharField(max_length=120)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    generation_mode = models.CharField(max_length=8)

    def __str__(self):
        return self.title


class Flashcard(models.Model):
    class Status(models.TextChoices):
        NEEDS_REVIEW = "needs_review", "Тексеру керек"
        REVIEWED = "reviewed", "Тексерілді"

    source = models.ForeignKey(
        Source,
        on_delete=models.CASCADE,
        related_name="cards",
    )
    position = models.PositiveSmallIntegerField()
    question = models.CharField(max_length=300)
    answer = models.TextField(max_length=1600)
    source_quote = models.TextField(max_length=1600)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEEDS_REVIEW,
    )

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "position"],
                name="unique_card_position",
            ),
        ]

    def __str__(self):
        return self.question
