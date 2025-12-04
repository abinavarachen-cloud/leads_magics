from django.contrib import admin
from .models import Company, Client, List

admin.site.site_header = "Leads Magics Admin"
admin.site.site_title = "Leads Magics Admin Portal"
admin.site.index_title = "Welcome to Leads Magics Admin Portal"

admin.site.register(Company)
admin.site.register(Client)
admin.site.register(List)  

