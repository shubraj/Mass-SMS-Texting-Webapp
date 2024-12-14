from django.contrib import admin
from .models import ContactMetrics,ContactGroup,Contact,Campaign,Message

@admin.register(ContactMetrics)
class ContactMetricsAdmin(admin.ModelAdmin):
    list_display = ('contact', 'messages_sent', 'messages_received', 'messages_failed', 'delivery_rate', 'last_message_date')
    readonly_fields = ('messages_sent', 'messages_received', 'messages_failed', 'last_message_date', 'delivery_rate')
    search_fields = ('contact__full_name', 'contact__phone_number')
    date_hierarchy = 'last_message_date'

@admin.register(ContactGroup)
class ContactGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'get_member_count', 'created_by', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'created_by')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone_number', 'email', 'status', 'created_at')
    list_filter = ('status', 'groups', 'created_at')
    search_fields = ('full_name', 'phone_number', 'email')
    filter_horizontal = ('groups',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Information', {
            'fields': ('full_name', 'phone_number', 'email')
        }),
        ('Status & Groups', {
            'fields': ('status', 'groups')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'campaign_type', 'status', 'created_by', 'created_at')
    list_filter = ('campaign_type', 'status', 'created_at')
    search_fields = ('name', 'message')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Campaign Information', {
            'fields': ('name', 'campaign_type', 'status')
        }),
        ('Message Details', {
            'fields': ('message', 'groups')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('contact', 'status', 'message', 'created_at', 'status_display')
    list_filter = ('status', 'created_at')
    search_fields = ('contact__phone_number', 'message')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Message Information', {
            'fields': ('contact', 'status', 'message')
        }),
        ('Metadata', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )