from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
from django.db.models import Sum
import random

class MessageMetricsManager:
    @staticmethod
    def get_total_system_metrics():
        """
        Calculate system-wide messaging metrics including engagement
        """
        # Get contact metrics totals
        contact_metrics = ContactMetrics.objects.aggregate(
            total_contact_sent=Sum('messages_sent'),
            total_contact_failed=Sum('messages_failed'),
            total_contact_received=Sum('messages_received')
        )
        

        
        # Calculate totals
        total_messages_sent = (
            (contact_metrics['total_contact_sent'] or 0)
        )
        
        total_messages_failed = (
            (contact_metrics['total_contact_failed'] or 0)
        )
        
        total_messages_received = contact_metrics['total_contact_received'] or 0
        total_messages_delivered = total_messages_sent - total_messages_failed
        
        # Calculate rates
        delivery_rate = 0
        engagement_rate = 0
        response_rate = 0
        
        if total_messages_sent > 0:
            delivery_rate = ((total_messages_sent - total_messages_failed) / 
                           total_messages_sent * 100)
            response_rate = (total_messages_received / total_messages_sent * 100)
            
            if total_messages_delivered > 0:
                engagement_rate = (total_messages_received / total_messages_delivered * 100)
        
        return {
            'total_messages_sent': total_messages_sent,
            'total_messages_failed': total_messages_failed,
            'total_messages_received': total_messages_received,
            'total_messages_delivered': total_messages_delivered,
            'overall_delivery_rate': round(delivery_rate, 2),
            'engagement_rate': round(engagement_rate, 2),
            'response_rate': round(response_rate, 2),
            'contact_metrics': contact_metrics
        }

    @staticmethod
    def get_group_metrics(group_id):
        """
        Calculate messaging metrics for a specific contact group including engagement
        """
        # Get contacts in the group
        contacts = Contact.objects.filter(groups=group_id)
        
        # Get contact metrics for the group
        contact_metrics = ContactMetrics.objects.filter(
            contact__in=contacts
        ).aggregate(
            total_sent=Sum('messages_sent'),
            total_failed=Sum('messages_failed'),
            total_received=Sum('messages_received')
        )
        
        
        # Calculate totals
        total_sent = contact_metrics['total_sent'] or 0
        
        total_failed = contact_metrics['total_failed'] or 0
        
        total_received = contact_metrics['total_received'] or 0
        total_delivered = total_sent - total_failed
        
        # Calculate rates
        delivery_rate = 0
        engagement_rate = 0
        response_rate = 0
        
        if total_sent > 0:
            delivery_rate = ((total_sent - total_failed) / total_sent * 100)
            response_rate = (total_received / total_sent * 100)
            
            if total_delivered > 0:
                engagement_rate = (total_received / total_delivered * 100)
            
        return {
            'total_messages_sent': total_sent,
            'total_messages_failed': total_failed,
            'total_messages_received': total_received,
            'total_messages_delivered': total_delivered,
            'delivery_rate': round(delivery_rate, 2),
            'engagement_rate': round(engagement_rate, 2),
            'response_rate': round(response_rate, 2)
        }

class ContactMetrics(models.Model):
    contact = models.OneToOneField('Contact', on_delete=models.CASCADE, related_name='metrics')
    
    # Message Metrics
    messages_sent = models.IntegerField(default=0)
    messages_received = models.IntegerField(default=0)
    messages_failed = models.IntegerField(default=0)
    last_message_date = models.DateTimeField(null=True, blank=True)
    
    # Update tracking
    updated_at = models.DateTimeField(auto_now=True)
    
    def delivery_rate(self):
        """Calculate the successful message delivery rate"""
        total_sent = self.messages_sent
        return ((total_sent - self.messages_failed) / total_sent * 100) if total_sent > 0 else 0

    
    def record_message_sent(self):
        """Record a new message sent to the contact"""
        self.messages_sent += 1
        self.last_message_date = timezone.now()
        self.save(update_fields=['messages_sent', 'last_message_date'])
    
    def record_message_failed(self):
        """Record a new message sent to the contact"""
        self.messages_failed += 1
        self.last_message_date = timezone.now()
        self.save(update_fields=['messages_failed', 'last_message_date'])
    
    def record_message_received(self):
        """Record a new message received from the contact"""
        self.messages_received += 1
        self.last_message_date = timezone.now()
        self.save(update_fields=['messages_received', 'last_message_date'])
    
    
    class Meta:
        verbose_name_plural = 'Contact metrics'
        indexes = [
            models.Index(fields=['last_message_date']),
        ]

    def __str__(self):
        return f"Metrics for {self.contact}"

class ContactGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    color = models.CharField(max_length=50, blank=True)  # New field for color

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    def get_member_count(self):
        return self.contacts.count()

    def save(self, *args, **kwargs):
        if not self.color:  # Only assign color if it's not set
            self.color = self.get_random_tailwind_color()
        super().save(*args, **kwargs)

    def get_random_tailwind_color(self):
        # List of Tailwind colors with good contrast
        colors = [
            'bg-red-100',
            'bg-blue-100',
            'bg-green-100', 
            'bg-yellow-100',
            'bg-indigo-100',
            'bg-pink-100',
            'bg-indigo-100',
            'bg-teal-100',
            'bg-orange-100',
            'bg-cyan-100'
        ]
        return random.choice(colors)

class Contact(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    phone_number_validator = RegexValidator(
        regex=r'^(\+1)?\d{10}$',
        message="Phone number must be in the format +1XXXXXXXXXX (US country code + number)"
    )

    full_name = models.CharField(max_length=255,null=True,blank=True)
    phone_number = models.CharField(
        max_length=17, 
        unique=True,
        validators=[phone_number_validator]
    )
    email = models.EmailField(null=True,blank=True)
    
    # Status and Groups
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    groups = models.ManyToManyField(ContactGroup, related_name='contacts', blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.phone_number})"
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES)[self.status]
    
    @property
    def is_active(self):
        return self.status == 'active'
    
    def save(self, *args, **kwargs):
        # Ensure phone number starts with +1
        if self.phone_number and not self.phone_number.startswith('+'):
            self.phone_number = f"+1{self.phone_number}"
        super().save(*args, **kwargs)
    

class Campaign(models.Model):
    CAMPAIGN_TYPES = [
        ('PROMO', 'Promotional Message'),
        ('EVENT', 'Event Announcement'),
        ('GIVE', 'Giveaway Campaign'),
    ]

    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('CANCELLED', 'Cancelled'),
    ]

    # Basic Campaign Information
    name = models.CharField(max_length=100,unique=True)
    campaign_type = models.CharField(max_length=5, choices=CAMPAIGN_TYPES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ACTIVE')
    
    # Message Content
    message = models.TextField(validators=[MaxLengthValidator(160)])
    groups = models.ManyToManyField(ContactGroup,related_name="campaigns",blank=True)
    
    # Metadata
    created_by = models.ForeignKey(User,related_name='campaigns',on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign_type', 'status']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_campaign_type_display})"
    
    @property
    def get_campaign_type_display(self):
        return dict(self.CAMPAIGN_TYPES)[self.campaign_type]
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES)[self.status]
    
    @property
    def get_recipients(self):
        return (
            Contact.objects
            .filter(groups__in=self.groups.all())
            .filter(status="active")
            .distinct()
            .count()
    )
class Message(models.Model):
    STATUS_CHOICES = (
        ("DELIVERED","Delivered"),
        ("FAILED","Failed"),
        ("RECEIVED","Received")
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='DELIVERED')
    message = models.TextField(validators=[MaxLengthValidator(160)])
    contact = models.ForeignKey(Contact,on_delete=models.CASCADE,related_name="messages")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.status}: {self.contact.phone_number}"
    
    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES)[self.status]
    @property
    def is_outbound(self):
        return self.status in ("DELIVERED","FAILED")
    
    