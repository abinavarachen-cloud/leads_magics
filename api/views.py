# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q

from .models import Company, Client, List
from .serializers import CompanySerializer, ClientSerializer, ListSerializer

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
            filters &= (
                Q(company__location__icontains=location) |
                Q(location__icontains=location)
            )
        
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
            media_url=original.media_url.copy() if original.media_url else {},
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
    
  