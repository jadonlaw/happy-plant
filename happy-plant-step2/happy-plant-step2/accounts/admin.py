from django.contrib import admin

from .models import EmailCode, Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "email_verified", "temp_unit", "created_at")
    list_filter = ("email_verified",)
    search_fields = ("user__email", "user__first_name")


@admin.register(EmailCode)
class EmailCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "purpose", "created_at", "expires_at", "attempts", "locked_until", "used_at")
    list_filter = ("purpose",)
    search_fields = ("user__email",)
    readonly_fields = ("user", "purpose", "code_hash", "created_at", "expires_at", "attempts", "used_at")
