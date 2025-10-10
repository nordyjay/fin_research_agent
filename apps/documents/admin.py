from django.contrib import admin
from .models import BrokerDocument

@admin.register(BrokerDocument)
class BrokerDocumentAdmin(admin.ModelAdmin):
    list_display = ['broker', 'ticker', 'report_date', 'processed', 'created_at']
    list_filter = ['processed', 'broker', 'ticker', 'report_date']
    search_fields = ['broker', 'ticker', 'title']
    readonly_fields = ['id', 'created_at', 'updated_at', 'processing_error']
    
    fieldsets = (
        ('Document Information', {
            'fields': ('file', 'broker', 'ticker', 'report_date', 'title')
        }),
        ('Processing Status', {
            'fields': ('processed', 'processing_error', 'total_pages', 'total_chunks', 'total_tables', 'total_images')
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at')
        }),
    )