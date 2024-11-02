from django.db import models
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from books.models import Book
from drf_library import settings


class Borrowing(models.Model):
    borrow_date = models.DateField(auto_now_add=True)
    expected_return_date = models.DateField()
    actual_return_date = models.DateField(null=True, blank=True, default=None)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="borrowings")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="borrowings",
    )

    @staticmethod
    def validate_dates(
        borrow_date, expected_return_date, actual_return_date, error_to_raise
    ):
        borrow_date = borrow_date or timezone.now().date()
        if borrow_date >= expected_return_date:
            raise error_to_raise(
                f"Borrow date should be earlier than expected return date. "
                f"Borrow date is {borrow_date}, "
                f"and expected return date is {expected_return_date}."
            )

        if actual_return_date and borrow_date >= actual_return_date:
            raise error_to_raise(
                f"Borrow date should be earlier than actual return date. "
                f"Borrow date is {borrow_date}, "
                f"and actual return date is {actual_return_date}."
            )

    def clean(self):
        Borrowing.validate_dates(
            self.borrow_date,
            self.expected_return_date,
            self.actual_return_date,
            ValidationError,
        )

    def save(self, *args, **kwargs):
        if self._state.adding:
            if self.book.inventory < 1:
                raise ValidationError("The book is not available.")
            self.full_clean()
            self.book.inventory -= 1
            self.book.save()
        super().save(*args, **kwargs)

    def return_book(self):
        if not self.actual_return_date:
            self.actual_return_date = timezone.now().date()
            self.book.inventory += 1
            self.book.save()
            self.save()

    def __str__(self):
        return f"{self.book} {self.borrow_date} — {self.expected_return_date}"
