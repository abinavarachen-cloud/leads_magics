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
    # All above are already implemented by ModelViewSet
    
    # 5. LIST WITH ALL FILTERS - GET /api/clients/
    def list(self, request):
        """List clients with ALL filters in one endpoint"""
        queryset = Client.objects.all()
        
        # Get all query parameters
        params = request.query_params
        
        # Build filter conditions
        filters = Q()
        
        # Search across multiple fields
        if search := params.get('search'):
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
            'results': serializer.data
        })
    
    # 6. CREATE DUPLICATE
    @action(detail=True, methods=['POST'])
    def duplicate(self, request, pk=None):
        """Create duplicate of a client - POST /api/clients/{id}/duplicate/"""
        original = self.get_object()
        
        # Create copy of all data
        client_data = ClientSerializer(original).data
        
        # Remove ID and timestamps
        client_data.pop('id', None)
        client_data.pop('created_at', None)
        client_data.pop('updated_at', None)
        
        # Add duplication note in remarks
        remarks = client_data.get('remarks', '')
        client_data['remarks'] = f"Duplicated from: {original.client}\n{remarks}"
        
        # Create new client
        serializer = ClientSerializer(data=client_data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # 7. SEARCH PEOPLE
    @action(detail=False, methods=['GET'])
    def search_people(self, request):
        """Search people - GET /api/clients/search_people/?q=search_term"""
        query = request.query_params.get('q', '').strip()
        
        if not query:
            return Response({'error': 'Search query (q) is required'}, status=400)
        
        results = Client.objects.filter(
            Q(client__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query) |
            Q(job_role__icontains=query)
        )
        
        serializer = ClientSerializer(results, many=True)
        return Response({
            'search_query': query,
            'count': results.count(),
            'results': serializer.data
        })

# ========== LIST API ==========
class ListViewSet(viewsets.ModelViewSet):
    queryset = List.objects.all()
    serializer_class = ListSerializer