from django.contrib import admin

from .models import Signup


@admin.register(Signup)
class SignupAdmin(admin.ModelAdmin):
    list_display = ("email", "created_at", "source", "confirmation_sent_at", "launch_sent_at")
    list_filter = ("source",)
    search_fields = ("email",)
    readonly_fields = ("created_at", "confirmation_sent_at", "launch_sent_at")
