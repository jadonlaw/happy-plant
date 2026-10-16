from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html

from accounts.emails import send_happy_key
from .models import Reading, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("serial", "happy_key", "owner", "name", "buyer_email", "key_sent_at", "last_seen")
    search_fields = ("serial", "happy_key", "owner__email", "buyer_email")
    readonly_fields = ("serial", "happy_key", "owner", "paired_at", "last_seen", "battery_pct", "key_sent_at",
                       "created_at")
    fields = ("serial", "happy_key", "buyer_email", "key_sent_at", "owner", "paired_at", "name", "power_mode",
              "last_seen", "battery_pct", "notes", "created_at")
    actions = ["email_happy_key", "remove_owner"]

    def save_model(self, request, obj, form, change):
        if not change:
            board_secret = obj.assign_identity()
            super().save_model(request, obj, form, change)
            self.message_user(request, format_html(
                "Created <b>{}</b> with Happy Key <b>{}</b>.<br>"
                "BOARD SECRET (shown only once, copy it into this unit's firmware now): <code>{}</code>",
                obj.serial, obj.happy_key, board_secret), messages.WARNING)
        else:
            super().save_model(request, obj, form, change)

    @admin.action(description="Email Happy Key to the buyer email")
    def email_happy_key(self, request, queryset):
        for unit in queryset:
            if not unit.buyer_email:
                self.message_user(request, f"{unit.serial}: add a buyer email first.", messages.ERROR)
                continue
            if send_happy_key(unit.buyer_email, unit.happy_key):
                unit.key_sent_at = timezone.now()
                unit.save(update_fields=["key_sent_at"])
                self.message_user(request, f"{unit.serial}: Happy Key emailed to {unit.buyer_email}.")
            else:
                self.message_user(request, f"{unit.serial}: email failed. Try again in a minute.", messages.ERROR)

    @admin.action(description="Remove owner (unit can be paired again)")
    def remove_owner(self, request, queryset):
        n = queryset.exclude(owner=None).update(owner=None, paired_at=None, name="", latitude=None, longitude=None)
        self.message_user(request, f"Removed the owner from {n} unit(s).")


@admin.register(Reading)
class ReadingAdmin(admin.ModelAdmin):
    list_display = ("unit", "received_at", "light_raw", "air_f", "moisture_raw", "soil_f", "battery_pct", "rssi")
    list_filter = ("unit",)
    date_hierarchy = "received_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
