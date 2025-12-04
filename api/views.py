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

