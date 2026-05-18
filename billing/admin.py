from django.contrib import admin

from .models import Invoice, Payment, Refund


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'enrollment', 'total_amount', 'status', 'due_date', 'paid_at')
    list_filter = ('status', 'currency')
    search_fields = ('invoice_number', 'enrollment__kelas__name')
    readonly_fields = ('total_amount', 'created_at', 'updated_at')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'gateway', 'status', 'paid_at')
    list_filter = ('status', 'method', 'gateway')
    search_fields = ('invoice__invoice_number', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('payment', 'invoice', 'amount', 'status', 'requested_by', 'approved_by')
    list_filter = ('status',)
    search_fields = ('invoice__invoice_number', 'gateway_refund_id')
    readonly_fields = ('created_at', 'updated_at')
