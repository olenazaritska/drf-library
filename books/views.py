from rest_framework.viewsets import ModelViewSet

from books.models import Book
from books.permissions import IsAdminOrReadOnly
from books.serializers import BookSerializer, BookListSerializer


class BookViewSet(ModelViewSet):
    queryset = Book.objects.all()
    permission_classes = [IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == "list":
            return BookListSerializer
        return BookSerializer
