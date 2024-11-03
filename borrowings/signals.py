from django.db.models.signals import post_save
from django.dispatch import receiver

from borrowings.models import Borrowing
from borrowings.tasks import send_notification


@receiver(post_save, sender=Borrowing)
def send_notification_on_borrowing_creation(sender, instance, created, **kwargs):
    if created:
        message = (
            f"A new borrowing has been created on {instance.borrow_date}.\n"
            f"Expected return date is {instance.expected_return_date}."
        )
        send_notification.delay(message)
