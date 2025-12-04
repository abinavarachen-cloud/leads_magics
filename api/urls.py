# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'clients', ClientViewSet)
router.register(r'lists', ListViewSet)
router.register(r'folders', FolderViewSet)

urlpatterns = [
    path('', include(router.urls)),
]