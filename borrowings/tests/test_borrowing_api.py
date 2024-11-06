from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from books.models import Book
from borrowings.models import Borrowing
from borrowings.serializers import BorrowingListSerializer

BORROWING_LIST_URL = reverse("borrowings:borrowing-list")
BORROWING_RETURN_URL = reverse("borrowings:borrowing-return-book", kwargs={"pk": 1})


def sample_book():
    return Book.objects.create(
        title="Test_title",
        author="Test_author",
        cover="HARD",
        inventory=5,
        daily_fee=2.05,
    )


class UnauthenticatedBorrowingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_required(self):
        response = self.client.get(BORROWING_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminBorrowingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_superuser(
            email="admin@test.com",
            password="test123",
        )
        self.client.force_authenticate(self.user)

    @mock.patch("borrowings.signals.send_notification.delay", return_value=None)
    def test_list_with_user_id_filter(self, mock_task):
        book = sample_book()
        non_admin_user = get_user_model().objects.create_user(
            email="test@test.com",
            password="test123",
        )
        borrowing_1 = Borrowing.objects.create(
            expected_return_date="2024-11-15", book=book, user=self.user
        )
        borrowing_2 = Borrowing.objects.create(
            expected_return_date="2024-11-16", book=book, user=non_admin_user
        )

        response = self.client.get(
            BORROWING_LIST_URL, {"user_id": str(non_admin_user.id)}
        )
        borrowings = Borrowing.objects.filter(user_id=int(non_admin_user.id))
        serializer = BorrowingListSerializer(borrowings, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)


class AuthenticatedBorrowingAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@test.com",
            password="test123",
        )
        self.client.force_authenticate(self.user)

    @mock.patch("borrowings.signals.send_notification.delay", return_value=None)
    def test_list_with_is_active_filter(self, mock_task):
        book = sample_book()
        borrowing_1 = Borrowing.objects.create(
            expected_return_date="2024-11-15", book=book, user=self.user
        )
        borrowing_2 = Borrowing.objects.create(
            expected_return_date="2024-11-16",
            actual_return_date="2024-11-10",
            book=book,
            user=self.user,
        )

        response = self.client.get(BORROWING_LIST_URL, {"is_active": "1"})
        borrowings = Borrowing.objects.filter(actual_return_date=None)
        serializer = BorrowingListSerializer(borrowings, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

        response = self.client.get(BORROWING_LIST_URL, {"is_active": "0"})
        borrowings = Borrowing.objects.exclude(actual_return_date=None)
        serializer = BorrowingListSerializer(borrowings, many=True)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, serializer.data)

    def test_borrowing_creation_fails_when_book_inventory_zero(self):
        book = sample_book()
        book.inventory = 0
        book.save()

        payload = {
            "expected_return_date": (
                timezone.now() + timezone.timedelta(days=10)
            ).date(),
            "book": book.id,
            "user": self.user.id,
        }

        response = self.client.post(BORROWING_LIST_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("The book is not available.", str(response.data))

    def test_expected_return_date_before_borrow_date_forbidden(self):
        book = sample_book()
        payload = {
            "expected_return_date": (
                timezone.now() - timezone.timedelta(days=1)
            ).date(),
            "book": book.id,
            "user": self.user.id,
        }

        response = self.client.post(BORROWING_LIST_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(
            "Borrow date should be earlier than expected return date",
            str(response.data),
        )

    @mock.patch("borrowings.signals.send_notification.delay", return_value=None)
    def test_book_inventory_decrements_on_borrowing_creation(self, mock_task):
        book = sample_book()
        initial_inventory = book.inventory

        payload = {
            "expected_return_date": (
                timezone.now() + timezone.timedelta(days=10)
            ).date(),
            "book": book.id,
            "user": self.user.id,
        }

        response = self.client.post(BORROWING_LIST_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        book.refresh_from_db()
        self.assertEqual(book.inventory, initial_inventory - 1)

    @mock.patch("borrowings.signals.send_notification.delay", return_value=None)
    def test_borrowing_cannot_be_returned_if_already_returned(self, mock_task):
        book = sample_book()
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=book,
            expected_return_date=timezone.now().date() + timezone.timedelta(days=10),
            actual_return_date=timezone.now().date() + timezone.timedelta(days=5),
        )

        response = self.client.post(BORROWING_RETURN_URL)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This book has already been returned.", response.data["detail"])

    @mock.patch("borrowings.signals.send_notification.delay", return_value=None)
    def test_borrowing_can_be_returned_and_inventory_increases(self, mock_task):
        book = sample_book()
        borrowing = Borrowing.objects.create(
            user=self.user,
            book=book,
            expected_return_date=timezone.now().date() + timezone.timedelta(days=10),
        )
        initial_inventory = book.inventory

        response = self.client.post(BORROWING_RETURN_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Book successfully returned.", response.data["detail"])

        book.refresh_from_db()
        borrowing.refresh_from_db()

        self.assertEqual(book.inventory, initial_inventory + 1)
        self.assertIsNotNone(borrowing.actual_return_date)
