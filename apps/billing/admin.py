from django.contrib import admin

from apps.billing.models import Invoice, Plan, Subscription, UsageRecord


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "price_monthly", "is_active", "sort_order"]
    list_editable = ["is_active", "sort_order"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["organization", "plan", "status", "current_period_end"]
    list_filter = ["status", "plan"]
    search_fields = ["organization__name"]


@admin.register(UsageRecord)
class UsageRecordAdmin(admin.ModelAdmin):
    list_display = ["organization", "metric", "period_start", "count"]
    list_filter = ["metric", "period_start"]
    search_fields = ["organization__name"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["organization", "status", "amount_due", "currency", "created_at"]
    list_filter = ["status"]
