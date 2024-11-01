from django.db import models


class Book(models.Model):
    COVER_CHOICES = {
        "HARD": "hard",
        "SOFT": "soft",
    }

    title = models.CharField(max_length=250)
    author = models.CharField(max_length=250)
    cover = models.CharField(
        max_length=50,
        choices=COVER_CHOICES,
    )
    inventory = models.PositiveIntegerField()
    daily_fee = models.DecimalField(max_digits=5, decimal_places=2)
