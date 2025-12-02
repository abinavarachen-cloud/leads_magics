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
from django.urls import path
from .views import (
    CampaignListCreateView,
    CampaignDetailView,
    CampaignGenerateRecipientsView,
    CampaignSendTestView,
    CampaignSendNowView,
    CampaignScheduleView,
)

urlpatterns = [
    path('campaigns/', CampaignListCreateView.as_view()),
    path('campaigns/<int:pk>/', CampaignDetailView.as_view()),

    # actions
    path('campaigns/<int:pk>/add-test-email/', CampaignSendTestView.as_view()),
    path('campaigns/<int:pk>/generate-recipients/', CampaignGenerateRecipientsView.as_view()),
    path('campaigns/<int:pk>/send-now/', CampaignSendNowView.as_view()),
    path('campaigns/<int:pk>/schedule/', CampaignScheduleView.as_view()),
]
