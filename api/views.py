# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
import csv
from django.http import HttpResponse
from rest_framework.decorators import action
from .models import *
from .serializers import *

# ========== COMPANY API ==========
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

# ========== CLIENT API ==========
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    
    # 1. CREATE - POST /api/clients/
    # 2. GET SINGLE - GET /api/clients/{id}/
    # 3. EDIT - PUT/PATCH /api/clients/{id}/
    # 4. DELETE - DELETE /api/clients/{id}/
    

    def list(self, request):
        """List clients with ALL filters in one endpoint"""
        queryset = Client.objects.all()
        
        # Get all query parameters
        params = request.query_params
        
        # Build filter conditions
        filters = Q()
        
        query = params.get('q', '').strip()
        search = params.get('search', '').strip()
        
        if query:  # Simple search using 'q'
            filters &= (
                Q(client__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(job_role__icontains=query)
            )
        
        if search:  # Advanced search using 'search'
            filters &= (
                Q(client__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(job_role__icontains=search) |
                Q(status__icontains=search) |
                Q(remarks__icontains=search) |
                Q(lead_owner__icontains=search) |
                Q(company__company_name__icontains=search) 
            )
        
        # Filter by role
        if role := params.get('role'):
            filters &= Q(job_role__icontains=role)
        
        # Filter by location (client location or company location)
        if location := params.get('location'):
            filters &= Q(company__location__icontains=location)

        
        # Filter by company name
        if company := params.get('company'):
            filters &= Q(company__company_name__icontains=company)
        
        # Filter by status
        if status := params.get('status'):
            filters &= Q(status__icontains=status)
        
        # Filter by remarks
        if remarks := params.get('remarks'):
            filters &= Q(remarks__icontains=remarks)
        
        # Filter by lead owner
        if lead_owner := params.get('lead_owner'):
            filters &= Q(lead_owner__icontains=lead_owner)
        
        # Filter by nurturing stage
        if nurturing_stage := params.get('nurturing_stage'):
            filters &= Q(nurturing_stage=nurturing_stage)
        
        # Filter by social media
        if params.get('has_social') == 'true':
            filters &= ~Q(social_media__isnull=True) & ~Q(social_media={})
        
        # Filter by specific social media platform
        if platform := params.get('social_media'):
            filters &= Q(social_media__has_key=platform)
        
        # Apply all filters at once
        queryset = queryset.filter(filters)
        
        # Return results
        serializer = ClientSerializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'filters_applied': {
                'q': query,
                'role': params.get('role'),
                'location': params.get('location'),
                'company': params.get('company'),
                'status': params.get('status'),
                'remarks': params.get('remarks'),
                'lead_owner': params.get('lead_owner'),
                'nurturing_stage': params.get('nurturing_stage'),
                'platform': params.get('platform')
            }
        })



    @action(detail=True, methods=['POST'])
    def duplicate(self, request, pk=None):
        """Create duplicate of a client - POST /api/clients/{id}/duplicate/"""
        original = self.get_object()
        
        # Create duplicate directly using the ORM
        duplicate = Client.objects.create(
            company=original.company,
            client=original.client,
            job_role=original.job_role,
            phone=original.phone,
            email=original.email,
            social_media=original.social_media.copy() if original.social_media else {},
            status=original.status,
            lead_owner=original.lead_owner,
            nurturing_stage=original.nurturing_stage,
            remarks=f"Duplicated from: {original.client}\n{original.remarks or ''}"
        )
        
        # Return the duplicated client
        serializer = ClientSerializer(duplicate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ========== LIST API ==========
class ListViewSet(viewsets.ModelViewSet):
    """List API with client operations"""
    queryset = List.objects.all()
    serializer_class = ListSerializer

    def get_queryset(self):
        """Filter lists by folder and search"""
        queryset = List.objects.all()
        params = self.request.query_params
        
        # Filter by folder
        if folder := params.get('folder'):
            try:
                folder_id = int(folder)
                queryset = queryset.filter(folder_id=folder_id)
            except ValueError:
                # Or if you want to filter by folder name:
                queryset = queryset.filter(folder__name__icontains=folder)
        
        # Search by list name or ID using 'q' parameter
        if search_query := params.get('q', '').strip():
            try:
                list_id = int(search_query)
                queryset = queryset.filter(
                    Q(id=list_id) |
                    Q(name__icontains=search_query)
                )
            except ValueError:
                queryset = queryset.filter(name__icontains=search_query)
        
        # Also support direct name search
        if name := params.get('name'):
            queryset = queryset.filter(name__icontains=name)
        
        # Order by latest first
        return queryset.order_by('-created_at')
    

    @action(detail=True, methods=['GET'])
    def get_clients(self, request, pk=None):
        list_obj = self.get_object()
        clients = list_obj.clients.all().select_related('company').prefetch_related('tags')
        
        # Create filter mapping for cleaner code
        filter_mapping = {
            'role': 'job_role__icontains',
            'location': 'company__location__icontains',
            'company': 'company__company_name__icontains',
            'media': 'social_media__icontains',
            'lead_owner': 'lead_owner__icontains',
            'status': 'status__icontains',
            'industry': 'company__industry__icontains',
        }
        
        # Apply all filters dynamically
        for param, field_lookup in filter_mapping.items():
            if value := request.query_params.get(param):
                if '__' in field_lookup:
                    # Handle related field lookups
                    clients = clients.filter(**{field_lookup: value})
                else:
                    clients = clients.filter(**{field_lookup: value})
        
        # Add ordering
        order_by = request.query_params.get('order_by', 'id')
        if order_by.lstrip('-') in ['name', 'email', 'job_role', 'company_name']:
            clients = clients.order_by(order_by)
        
        # Pagination
        page = self.paginate_queryset(clients)
        if page is not None:
            serializer = ClientSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response({
                'list_id': list_obj.id,
                'list_name': list_obj.name,
                'total_clients': list_obj.count,
                'applied_filters': {k: v for k, v in request.query_params.items() if k in filter_mapping},
                'clients': serializer.data
            })
        
        serializer = ClientSerializer(clients, many=True, context={'request': request})
        return Response({
            'list_id': list_obj.id,
            'list_name': list_obj.name,
            'total_clients': list_obj.count,
            'filtered_count': clients.count(),
            'clients': serializer.data
        })


    # 1. ADD CLIENTS TO LIST
    @action(detail=True, methods=['POST'])
    def add_clients(self, request, pk=None):
        """Add clients to list"""
        list_obj = self.get_object()
        client_ids = request.data.get('client_ids', [])
        
        if not client_ids:
            return Response({'error': 'client_ids required'}, status=400)
        
        clients = Client.objects.filter(id__in=client_ids)
        list_obj.clients.add(*clients)
        list_obj.refresh_from_db()
        
        return Response({
            'message': f'Added {clients.count()} clients to list',
            'list': ListSerializer(list_obj).data
        })
    
    # 2. REMOVE CLIENTS FROM LIST
    @action(detail=True, methods=['POST'])
    def remove_clients(self, request, pk=None):
        """Remove clients from list"""
        list_obj = self.get_object()
        client_ids = request.data.get('client_ids', [])
        
        if not client_ids:
            return Response({'error': 'client_ids required'}, status=400)
        
        list_obj.clients.remove(*client_ids)
        list_obj.refresh_from_db()
        
        return Response({
            'message': f'Removed clients from list',
            'list': ListSerializer(list_obj).data
        })
    

    @action(detail=True, methods=['POST'])
    def duplicate(self, request, pk=None):
        """Duplicate a list with its clients"""
        original = self.get_object()
        
        new_name = request.data.get('name', '').strip()
        
        if not new_name:
            new_name = f"{original.name} (Copy)"
        
        # Create the duplicate list
        duplicate = List.objects.create(
            name=new_name,
            folder=original.folder
        )
        
        # Copy all clients from original to duplicate
        original_clients = original.clients.all()
        duplicate.clients.add(*original_clients)
        
        serializer = ListSerializer(duplicate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    

    @action(detail=True, methods=['POST'])
    def move(self, request, pk=None):
        """Merge clients from one list to another"""
        source_list = self.get_object()
        target_list_id = request.data.get('target_list_id')
        
        if not target_list_id:
            return Response({'error': 'target_list_id required'}, status=400)
        
        try:
            target_list = List.objects.get(id=target_list_id)
        except List.DoesNotExist:
            return Response({'error': 'Target list not found'}, status=404)
        
        # Don't allow copying to same list
        if source_list.id == target_list.id:
            return Response({'error': 'Cannot copy to same list'}, status=400)
        
        # Count before merge
        before_count = target_list.clients.count()
        
        # Merge clients (add() ignores duplicates)
        source_clients = source_list.clients.all()
        target_list.clients.add(*source_clients)
        
        # Count after merge
        target_list.refresh_from_db()
        after_count = target_list.clients.count()
        
        added = after_count - before_count
        
        return Response({
            'success': True,
            'message': f'Added {added} clients to {target_list.name}',
            'added_count': added,
            'source_list': source_list.name,
            'target_list': target_list.name
        })


    @action(detail=True, methods=['GET'])
    def export_clients(self, request, pk=None):
        """Export list clients to CSV"""
        list_obj = self.get_object()
        clients = list_obj.clients.all().select_related('company')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{list_obj.name}_clients.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Job Role', 'Company', 'Location', 'Phone', 'Social Media'])
        
        for client in clients:
            writer.writerow([
                client.name,
                client.email,
                client.job_role,
                client.company.company_name if client.company else '',
                client.company.location if client.company else '',
                client.phone,
                client.social_media
            ])
        
        return response


class FolderViewSet(viewsets.ModelViewSet):
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
from rest_framework import generics, status
from rest_framework import viewsets, status, generics, filters
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.conf import settings
from django.utils.html import strip_tags
from urllib.parse import unquote
import base64
from django.db import transaction
from rest_framework import filters  # Add this

from .models import *
from .serializers import *
from .tasks import *


# ========== COMPANY API ==========
class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer


# ========== CLIENT API ==========
class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    
    def list(self, request):
        """List clients with ALL filters in one endpoint"""
        queryset = Client.objects.all()
        
        # Get all query parameters
        params = request.query_params
        
        # Build filter conditions
        filters = Q()
        
        query = params.get('q', '').strip()
        search = params.get('search', '').strip()
        
        if query:  # Simple search using 'q'
            filters &= (
                Q(client__icontains=query) |
                Q(email__icontains=query) |
                Q(phone__icontains=query) |
                Q(job_role__icontains=query)
            )
        
        if search:  # Advanced search using 'search'
            filters &= (
                Q(client__icontains=search) |
                Q(email__icontains=search) |
                Q(phone__icontains=search) |
                Q(job_role__icontains=search) |
                Q(status__icontains=search) |
                Q(remarks__icontains=search) |
                Q(lead_owner__icontains=search) |
                Q(company__company_name__icontains=search)
            )
        
        # Filter by role
        if role := params.get('role'):
            filters &= Q(job_role__icontains=role)
        
        # Filter by location (client location or company location)
        if location := params.get('location'):
            filters &= (
                Q(company__location__icontains=location) |
                Q(location__icontains=location)
            )
        
        # Filter by company name
        if company := params.get('company'):
            filters &= Q(company__company_name__icontains=company)
        
        # Filter by status
        if status_param := params.get('status'):
            filters &= Q(status__icontains=status_param)
        
        # Filter by remarks
        if remarks := params.get('remarks'):
            filters &= Q(remarks__icontains=remarks)
        
        # Filter by lead owner
        if lead_owner := params.get('lead_owner'):
            filters &= Q(lead_owner__icontains=lead_owner)
        
        # Filter by nurturing stage
        if nurturing_stage := params.get('nurturing_stage'):
            filters &= Q(nurturing_stage=nurturing_stage)
        
        # Filter by social media
        if params.get('has_social') == 'true':
            filters &= ~Q(social_media__isnull=True) & ~Q(social_media={})
        
        # Filter by specific social media platform
        if platform := params.get('platform'):
            filters &= Q(social_media__has_key=platform)
        
        # Apply all filters at once
        queryset = queryset.filter(filters)
        
        # Return results
        serializer = ClientSerializer(queryset, many=True)
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'filters_applied': {
                'q': query,
                'role': params.get('role'),
                'location': params.get('location'),
                'company': params.get('company'),
                'status': params.get('status'),
                'remarks': params.get('remarks'),
                'lead_owner': params.get('lead_owner'),
                'nurturing_stage': params.get('nurturing_stage'),
                'platform': params.get('platform')
            }
        })

    @action(detail=True, methods=['POST'])
    def duplicate(self, request, pk=None):
        """Create duplicate of a client - POST /api/clients/{id}/duplicate/"""
        original = self.get_object()
        
        # Create duplicate directly using the ORM
        duplicate = Client.objects.create(
            company=original.company,
            client=original.client,
            job_role=original.job_role,
            phone=original.phone,
            email=original.email,
            social_media=original.social_media.copy() if original.social_media else {},
            status=original.status,
            lead_owner=original.lead_owner,
            nurturing_stage=original.nurturing_stage,
            remarks=f"Duplicated from: {original.client}\n{original.remarks or ''}"
        )
        
        # Return the duplicated client
        serializer = ClientSerializer(duplicate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ========== LIST API ==========
class ListViewSet(viewsets.ModelViewSet):
    """List API with client operations"""
    queryset = List.objects.all()
    serializer_class = ListSerializer
    
    # 1. ADD CLIENTS TO LIST
    @action(detail=True, methods=['POST'])
    def add_clients(self, request, pk=None):
        """Add clients to list"""
        list_obj = self.get_object()
        client_ids = request.data.get('client_ids', [])
        
        if not client_ids:
            return Response({'error': 'client_ids required'}, status=400)
        
        clients = Client.objects.filter(id__in=client_ids)
        list_obj.clients.add(*clients)
        list_obj.refresh_from_db()
        
        return Response({
            'message': f'Added {clients.count()} clients to list',
            'list': ListSerializer(list_obj).data
        })
    
    # 2. REMOVE CLIENTS FROM LIST
    @action(detail=True, methods=['POST'])
    def remove_clients(self, request, pk=None):
        """Remove clients from list"""
        list_obj = self.get_object()
        client_ids = request.data.get('client_ids', [])
        
        if not client_ids:
            return Response({'error': 'client_ids required'}, status=400)
        
        list_obj.clients.remove(*client_ids)
        list_obj.refresh_from_db()
        
        return Response({
            'message': f'Removed clients from list',
            'list': ListSerializer(list_obj).data
        })


# ========== EMAIL TEMPLATES & CATEGORIES ==========
class EmailTemplateCategoryListCreateView(generics.ListCreateAPIView):
    queryset = EmailTemplateCategory.objects.all()
    serializer_class = EmailTemplateCategorySerializer


class EmailTemplateCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EmailTemplateCategory.objects.all()
    serializer_class = EmailTemplateCategorySerializer


class EmailTemplateListCreateView(generics.ListCreateAPIView):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer


class EmailTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EmailTemplate.objects.all()
    serializer_class = EmailTemplateSerializer


# ========== EMAIL CAMPAIGNS ==========

class CampaignListCreateView(generics.ListCreateAPIView):
    queryset = EmailCampaign.objects.all()
    serializer_class = EmailCampaignSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'campaign_type']  # Add more fields as needed
    search_fields = ['campaign_name', 'subject_line', 'preview_text']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Get query parameters
        status = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        campaign_type = self.request.query_params.get('campaign_type')
        sender_email = self.request.query_params.get('sender_email')
        
        # Build filter conditions
        filter_conditions = Q()
        
        # Filter by status (exact match)
        if status:
            filter_conditions &= Q(status=status)
        
        # Filter by campaign_type (exact match)
        if campaign_type:
            filter_conditions &= Q(campaign_type=campaign_type)
        
        # Filter by sender_email (contains)
        if sender_email:
            filter_conditions &= Q(sender_email__icontains=sender_email)
        
        # Apply search across multiple fields (if search parameter provided)
        if search:
            search_condition = (
                Q(campaign_name__icontains=search) |
                Q(subject_line__icontains=search) |
                Q(preview_text__icontains=search) |
                Q(sender_name__icontains=search) |
                Q(sender_email__icontains=search)
            )
            filter_conditions &= search_condition
        
        # Apply all filters
        if filter_conditions:
            queryset = queryset.filter(filter_conditions)
        
        # Order by latest first
        queryset = queryset.order_by('-created_at')
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        # Get the filtered queryset
        queryset = self.filter_queryset(self.get_queryset())
        
        # Pagination (optional)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        
        # Add filter metadata to response
        return Response({
            'count': queryset.count(),
            'results': serializer.data,
            'filters_applied': {
                'status': request.query_params.get('status'),
                'search': request.query_params.get('search'),
                'campaign_type': request.query_params.get('campaign_type'),
                'sender_email': request.query_params.get('sender_email')
            }
        })


class CampaignDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EmailCampaign.objects.all()
    serializer_class = EmailCampaignSerializer
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Prevent deleting if campaign is sending or sent
        if instance.status in ['sending', 'sent']:
            return Response(
                {"error": f"Cannot delete a campaign that is {instance.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        self.perform_destroy(instance)
        return Response(
            {"message": f"Campaign '{instance.campaign_name}' deleted successfully"},
            status=status.HTTP_200_OK
        )


class CampaignActionView(APIView):
    
    def post(self, request):

        action = request.data.get('action', 'save_draft')
        
        # Validate campaign data first
        campaign_serializer = EmailCampaignSerializer(data=request.data.get('campaign', {}))
        campaign_serializer.is_valid(raise_exception=True)
        
        # Check action-specific requirements BEFORE creating campaign
        if action in ['send_test', 'send_now', 'schedule']:
            campaign_data = campaign_serializer.validated_data
            
            # Check if sender_email is provided for sending actions
            if not campaign_data.get('sender_email'):
                return Response(
                    {"error": "sender_email is required for this action"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if contact_lists are provided for sending actions
            if action in ['send_now', 'schedule'] and not campaign_data.get('contact_lists'):
                return Response(
                    {"error": "contact_lists is required for this action"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        with transaction.atomic():
            # Create campaign with initial status
            initial_status = 'draft' if action == 'save_draft' else 'draft'
            campaign = campaign_serializer.save(status=initial_status)
            
            # Perform the requested action
            return self._perform_action(campaign, action, request.data)
    
    def put(self, request, pk):
        """Update existing campaign and optionally perform an action"""
        action = request.data.get('action', 'save_draft')
        
        try:
            campaign = EmailCampaign.objects.get(pk=pk)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update campaign
        campaign_serializer = EmailCampaignSerializer(
            campaign, 
            data=request.data.get('campaign', {}), 
            partial=True
        )
        campaign_serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            campaign = campaign_serializer.save()
            
            # Perform the requested action
            return self._perform_action(campaign, action, request.data)
    
    def _perform_action(self, campaign, action, data):
        """Execute the specified action on the campaign"""
        
        if action == 'save_draft':
            return self._save_draft(campaign)
        
        elif action == 'send_test':
            return self._send_test(campaign, data)
        
        elif action == 'send_now':
            return self._send_now(campaign, data)
        
        elif action == 'schedule':
            return self._schedule(campaign, data)
        
        else:
            return Response(
                {"error": f"Invalid action: {action}"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _save_draft(self, campaign):
        """Save campaign as draft"""
        campaign.status = 'draft'
        campaign.save(update_fields=['status', 'updated_at'])
        
        return Response({
            "message": "Campaign saved as draft",
            "campaign_id": campaign.id,
            "status": campaign.status
        }, status=status.HTTP_200_OK)
    
    def _send_test(self, campaign, data):
        """Send test emails"""
        test_data = data.get('test_data', {})
        serializer = CampaignSendTestSerializer(data=test_data)
        serializer.is_valid(raise_exception=True)
        
        test_emails = serializer.validated_data["test_email"]
        
        # Validate campaign
        if not campaign.sender_email:
            return Response(
                {"error": "Campaign must have a sender email"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update test email recipients
        current = campaign.test_email_recipients or ""
        new_emails = ','.join(test_emails)
        campaign.test_email_recipients = f"{current},{new_emails}".strip(',')
        campaign.status = "send_test_email"
        campaign.save()
        
        # Send test emails
        task = send_test_emails_multiple.delay(campaign.id, test_emails)
        # task = send_test_email.delay(campaign.id, test_emails=test_emails)
        
        return Response({
            "message": f"Test emails sent to {len(test_emails)} recipients",
            "emails": test_emails,
            "campaign_id": campaign.id,
            "task_id": task.id,
            "status": campaign.status
        }, status=status.HTTP_200_OK)
    
    def _send_now(self, campaign, data):
        """Send campaign immediately"""
        send_data = data.get('send_data', {})
        serializer = CampaignSendNowSerializer(data=send_data)
        serializer.is_valid(raise_exception=True)

        if not serializer.validated_data.get('confirm'):
            return Response(
                {"error": "Please confirm to send the campaign"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate campaign
        if not campaign.sender_email:
            return Response(
                {"error": "Campaign must have a sender email"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not campaign.contact_lists.exists():
            return Response(
                {"error": "Campaign must have at least one contact list"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate recipients if they don't exist
        if campaign.recipients.count() == 0:
            self._generate_recipients(campaign)

        # Check if there are recipients
        pending_recipients = campaign.recipients.filter(status='pending').count()
        if pending_recipients == 0:
            return Response(
                {"error": "No pending recipients to send emails to"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update campaign status to "sending" (not "sent" yet)
        campaign.status = "sending"  # ← Changed from "sent"
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=["status", "sent_at", "updated_at"])

        # Queue emails for sending
        send_campaign_emails.delay(campaign.id)

        return Response({
            "message": f"Campaign is being sent to {pending_recipients} recipients",
            "campaign_id": campaign.id,
            "total_recipients": pending_recipients,
            "status": campaign.status,  # Will be "sending"
            "sent_at": campaign.sent_at
        }, status=status.HTTP_200_OK)
    
    def _schedule(self, campaign, data):
        """Schedule campaign for later"""
        schedule_data = data.get('schedule_data', {})
        serializer = CampaignScheduleSerializer(data=schedule_data)
        serializer.is_valid(raise_exception=True)

        scheduled_time = serializer.validated_data["scheduled_at"]

        # Validate scheduled time
        if scheduled_time <= timezone.now():
            return Response(
                {"error": "Scheduled time must be in the future"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Validate campaign
        if not campaign.sender_email:
            return Response(
                {"error": "Campaign must have a sender email"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        if not campaign.contact_lists.exists():
            return Response(
                {"error": "Campaign must have at least one contact list"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update campaign
        campaign.status = "scheduled"
        campaign.scheduled_at = scheduled_time
        campaign.save(update_fields=['status', 'scheduled_at', 'updated_at'])

        return Response({
            "message": f"Campaign scheduled for {scheduled_time}",
            "campaign_id": campaign.id,
            "scheduled_at": campaign.scheduled_at,
            "status": campaign.status
        }, status=status.HTTP_200_OK)
    
    def _generate_recipients(self, campaign):
        """Helper method to generate recipients for a campaign"""
        # Get clients from contact lists
        included = Client.objects.filter(
            lists__in=campaign.contact_lists.all()
        ).distinct()

        # Exclude clients from do-not-send lists
        excluded = Client.objects.filter(
            lists__in=campaign.do_not_send_lists.all()
        )

        # Final recipient list (with valid emails)
        final = included.exclude(id__in=excluded).exclude(
            email__isnull=True
        ).exclude(email='')

        # Create recipients
        for contact in final:
            EmailRecipient.objects.get_or_create(
                campaign=campaign,
                contact=contact,
                defaults={'status': 'pending'}
            )


class CampaignGenerateRecipientsView(APIView):
    """Standalone view to preview recipients before taking action"""
    
    def post(self, request, pk):
        try:
            campaign = EmailCampaign.objects.get(pk=pk)
        except EmailCampaign.DoesNotExist:
            return Response(
                {"error": "Campaign not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Get clients from contact lists
        included = Client.objects.filter(
            lists__in=campaign.contact_lists.all()
        ).distinct()

        # Exclude clients from do-not-send lists
        excluded = Client.objects.filter(
            lists__in=campaign.do_not_send_lists.all()
        )

        # Final recipient list
        recipients = included.exclude(id__in=excluded)
        recipients = recipients.exclude(email__isnull=True).exclude(email='')

        # Create EmailRecipient objects
        created = 0
        for contact in recipients:
            _, was_created = EmailRecipient.objects.get_or_create(
                campaign=campaign,
                contact=contact,
                defaults={'status': 'pending'}
            )
            if was_created:
                created += 1

        return Response({
            "message": "Recipients generated successfully",
            "total_created": created,
            "total_recipients": campaign.recipients.count()
        })

 
# ========== EMAIL TRACKING VIEWS ==========
@require_GET
def track_email_open(request, tracking_id):
    """
    Track when an email is opened (via tracking pixel)
    Returns a 1x1 transparent GIF
    """
    print(f"Email tracking triggered for ID: {tracking_id}")
    print(f"Tracking open for {tracking_id} at {timezone.now()}")

    try:
        recipient = get_object_or_404(EmailRecipient, tracking_id=tracking_id)

        # Always update the opened_at time to track repeated opens
        recipient.opened_at = timezone.now()
        recipient.status = 'opened'
        recipient.save()

        print(f"Tracked email open for recipient ID: {recipient.id}, email: {recipient.contact.email}")

        # Also update the associated contact's status from 'data' to 'lead'
        contact = recipient.contact
        if contact and contact.status == 'data':
            contact.status = 'lead'
            contact.save()
            print(f"Updated contact {contact.id} status from 'data' to 'lead'")
    except Exception as e:
        print(f"Error in tracking pixel: {str(e)}")

    # Return transparent 1x1 pixel with anti-caching headers
    response = HttpResponse(
        b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
        content_type='image/gif'
    )

    # Add headers to prevent caching
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'

    return response


@require_GET
def track_link_click(request, tracking_id):
    """
    Track when a link in an email is clicked and redirect to the original URL
    """
    try:
        recipient = get_object_or_404(EmailRecipient, tracking_id=tracking_id)
        original_url = unquote(request.GET.get('url', ''))

        if not original_url:
            print(f"No URL provided in tracking link (tracking_id: {tracking_id})")
            return redirect(getattr(settings, 'DOMAIN', 'http://localhost:8000'))

        # Update recipient status to 'clicked'
        recipient.clicked_at = timezone.now()
        recipient.status = 'clicked'
        recipient.save()

        # Update contact status to 'prospect' if it's currently 'data' or 'lead'
        if recipient.contact:
            if recipient.contact.status in ['data', 'lead']:
                recipient.contact.status = 'prospect'
                recipient.contact.save()

        print(f"Link clicked by {recipient.contact.email} - redirecting to {original_url}")

        return redirect(original_url)

    except Exception as e:
        print(f"Error tracking link click: {str(e)}")
        return redirect(getattr(settings, 'DOMAIN', 'http://localhost:8000'))


def unsubscribe(request, tracking_id):
    """
    Handle unsubscribe requests using the existing tracking_id
    """
    try:
        recipient = get_object_or_404(EmailRecipient, tracking_id=tracking_id)

        # Update contact status
        contact = recipient.contact
        if contact:
            contact.status = 'unsubscribed'
            contact.save()

        # Update recipient status
        recipient.unsubscribed_at = timezone.now()
        recipient.status = 'unsubscribed'
        recipient.save()

        # Render simple success message
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Unsubscribed Successfully</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                .success { color: green; font-size: 24px; }
                .message { margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="success">✓ Unsubscribed Successfully</div>
            <div class="message">You have been unsubscribed from our mailing list.</div>
            <div>You will no longer receive emails from us.</div>
        </body>
        </html>
        """
        return HttpResponse(html_content)
        
    except Exception as e:
        print(f"Error processing unsubscribe: {str(e)}")
        return HttpResponse("Error processing unsubscribe request", status=400)


# ========== EMAIL PREVIEW ==========
class EmailPreviewView(APIView):
    """
    Preview email content with personalization
    """
    def get(self, request, pk=None):
        try:
            if pk:
                # Preview specific campaign
                campaign = EmailCampaign.objects.get(pk=pk)
                subject = campaign.get_email_subject()
                html_content = campaign.get_email_content()
            else:
                # Preview with custom data
                template_id = request.GET.get('template_id')
                if template_id:
                    template = EmailTemplate.objects.get(id=template_id)
                    subject = template.subject or "Preview Subject"
                    html_content = template.content or ""
                else:
                    return Response(
                        {"error": "Either campaign_id or template_id is required"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Personalize with test data
            test_data = {
                '{{name}}': 'Test Recipient',
                '{{email}}': 'test@example.com',
                '{{company}}': 'Test Company',
                '{{job_role}}': 'Test Role',
            }
            
            for placeholder, value in test_data.items():
                subject = subject.replace(placeholder, value)
                html_content = html_content.replace(placeholder, value)
            
            return Response({
                'subject': subject,
                'html_content': html_content,
                'text_content': strip_tags(html_content)
            })
            
        except (EmailCampaign.DoesNotExist, EmailTemplate.DoesNotExist):
            return Response(
                {"error": "Campaign or template not found"},
                status=status.HTTP_404_NOT_FOUND
            )
            
            
# ========== TEMPLATE PREVIEW ==========
class TemplatePreviewView(APIView):
    """Get template content for preview"""
    def get(self, request):
        template_id = request.GET.get('template_id')
        
        if not template_id:
            return Response(
                {"error": "template_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            template = EmailTemplate.objects.get(id=template_id)
            return Response({
                'id': template.id,
                'name': template.name,
                'subject': template.subject,
                'content': template.content,
                'category': template.category.name if template.category else None
            })
        except EmailTemplate.DoesNotExist:
            return Response(
                {"error": "Template not found"},
                status=status.HTTP_404_NOT_FOUND
            )