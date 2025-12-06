from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'clients', ClientViewSet)
router.register(r'lists', ListViewSet)
router.register(r'folders', FolderViewSet)


urlpatterns = [
    path("login/", MyTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path('', include(router.urls)),
    
    # Email Templates (Fixed)
    path('templates/', TemplateListCreateView.as_view()),
    path('templates/<int:pk>/', TemplateDetailView.as_view()),
    path('templates/preview/', TemplatePreviewView.as_view()),
    
    # Campaigns - Unified Action View
    path('campaigns/', CampaignListCreateView.as_view()),
    path('campaigns/action/', CampaignActionView.as_view()),
    path('campaigns/<int:pk>/', CampaignDetailView.as_view()),
    path('campaigns/<int:pk>/action/', CampaignActionView.as_view()),
    path('campaigns/<int:pk>/generate-recipients/', CampaignGenerateRecipientsView.as_view()),
    path('campaigns/<int:pk>/preview/', EmailPreviewView.as_view()),
    path('campaigns/<int:pk>/preview-html/', EmailPreviewHTMLView.as_view()),  # NEW: Full HTML preview
    path('campaigns/preview/', EmailPreviewView.as_view()),
    path('campaigns/<int:pk>/send/', EmailSendView.as_view(), name='campaign-send'),
    path('campaigns/<int:pk>/preview-full/', EmailPreviewAPIView.as_view(), name='email-preview'),
    path('campaigns/<int:pk>/analytics/', CampaignAnalyticsView.as_view(), name='campaign-analytics'),
    
    # Tracking
    path('track/open/<uuid:tracking_id>/', track_email_open, name='track_email_open'),
    path('track/click/<uuid:tracking_id>/', track_link_click, name='track_link_click'),
    path('unsubscribe/<uuid:tracking_id>/', unsubscribe, name='unsubscribe'),
]