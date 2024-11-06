from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from borrowings.models import Borrowing
from borrowings.serializers import (
    BorrowingDetailSerializer,
    BorrowingListSerializer,
    BorrowingSerializer,
    BorrowingReturnSerializer,
)


class BorrowingViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    GenericViewSet,
):
    queryset = Borrowing.objects.select_related("book", "user")
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        queryset = Borrowing.objects.select_related("book", "user")

        user = self.request.user
        if not user.is_superuser:
            queryset = queryset.filter(user=self.request.user)

        is_active = self.request.query_params.get("is_active")
        user_id = self.request.query_params.get("user_id")

        if is_active == "1":
            queryset = queryset.filter(actual_return_date=None)
        elif is_active == "0":
            queryset = queryset.exclude(actual_return_date=None)

        if user_id and user.is_superuser:
            queryset = queryset.filter(user_id=int(user_id))

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return BorrowingDetailSerializer
        elif self.action == "list":
            return BorrowingListSerializer
        elif self.action == "create":
            return BorrowingSerializer
        return BorrowingReturnSerializer

    @extend_schema(
        request=BorrowingReturnSerializer,
        description="Marks a book as returned if it hasn't been returned yet.",
        responses={
            200: {"description": "Book successfully returned."},
            400: {"description": "This book has already been returned."},
        },
    )
    @action(detail=True, methods=["post"], url_path="return")
    def return_book(self, request, pk=None):
        borrowing = self.get_object()
        if borrowing.actual_return_date:
            return Response(
                {"detail": "This book has already been returned."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        borrowing.return_book()
        return Response(
            {"detail": "Book successfully returned."}, status=status.HTTP_200_OK
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="is_active",
                description="Filter by the borrowing active status, "
                "ex. 1 - not yet returned, 0 - already returned",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="user_id",
                description="Filter by user id (available only for admin users)",
                required=False,
                type=str,
            ),
        ]
    )
    def list(self, request, *args, **kwargs):
        return super().list(self, request, *args, **kwargs)
