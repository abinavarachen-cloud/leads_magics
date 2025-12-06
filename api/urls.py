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
    # CampaignSendTestView,
    # CampaignSendNowView,
    # CampaignScheduleView,
)

urlpatterns = [
    path("login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path('', include(router.urls)),
    
    # Email Template Categories
    path('template-categories/', EmailTemplateCategoryListCreateView.as_view()),
    path('template-categories/<int:pk>/', EmailTemplateCategoryDetailView.as_view()),
    
    # Email Templates
    path('templates/', EmailTemplateListCreateView.as_view()),
    path('templates/<int:pk>/', EmailTemplateDetailView.as_view()),
    path('templates/preview/', TemplatePreviewView.as_view()),
    
    # Campaigns - Unified Action View
    path('campaigns/', CampaignListCreateView.as_view()),
    path('campaigns/action/', CampaignActionView.as_view()),  # NEW: Create + Action
    path('campaigns/<int:pk>/', CampaignDetailView.as_view()),
    path('campaigns/<int:pk>/action/', CampaignActionView.as_view()),  # NEW: Update + Action
    path('campaigns/<int:pk>/generate-recipients/', CampaignGenerateRecipientsView.as_view()),
    path('campaigns/<int:pk>/preview/', EmailPreviewView.as_view()),
    path('campaigns/preview/', EmailPreviewView.as_view()),
    
    # Tracking
    path('track/open/<uuid:tracking_id>/', track_email_open, name='track_email_open'),
    path('track/click/<uuid:tracking_id>/', track_link_click, name='track_link_click'),
    path('unsubscribe/<uuid:tracking_id>/', unsubscribe, name='unsubscribe'),
]