from django.contrib import admin
from .models import Company, Client, List
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

admin.site.site_header = "Leads Magics Admin"
admin.site.site_title = "Leads Magics Admin Portal"
admin.site.index_title = "Welcome to Leads Magics Admin Portal"


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("email", "is_staff", "is_active")
    list_filter = ("is_staff", "is_active")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions")}),
        ("Extra", {"fields": ("is_admin", "is_partner", "otp", "company_id", "is_module_user")}),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_active"),
        }),
    )

    search_fields = ("email",)
    ordering = ("email",)

admin.site.register(Company)
admin.site.register(Client)
admin.site.register(List)
admin.site.register(CustomUser, CustomUserAdmin)
