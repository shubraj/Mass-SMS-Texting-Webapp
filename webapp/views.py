from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from .forms import EmailOrUsernameAuthenticationForm
from django.core.paginator import Paginator
from .models import Contact, ContactGroup, Campaign, MessageMetricsManager, Message, ContactMetrics
from django.db.models import Q, Subquery, OuterRef
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from .utils import send_message
from django.core.exceptions import ObjectDoesNotExist
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from io import StringIO
import csv
import re
import logging

# Initialize loggers
logger = logging.getLogger('webapp')
auth_logger = logging.getLogger('webapp.auth')
sms_logger = logging.getLogger('webapp.sms')

class CurrentPageMixin:
    """Mixin to track current page in navigation."""
    current_page = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["user"] = self.request.user
        context['current_page'] = self.current_page
        return context

class CustomLoginView(LoginView):
    """Custom login view supporting both email and username authentication."""
    template_name = 'webapp/login.html'
    authentication_form = EmailOrUsernameAuthenticationForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            auth_logger.info(f"Authenticated user {request.user} redirected from login")
            return redirect('app_webapp:dashboard')
        return super().dispatch(request, *args, **kwargs)

class CustomLogoutView(LoginRequiredMixin, LogoutView):
    """Handle user logout with redirection."""
    next_page = 'app_webapp:login'
    template_name = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            auth_logger.warning("Unauthenticated user attempted to access logout")
            return redirect('app_webapp:login')
        auth_logger.info(f"User {request.user} logged out")
        return super().dispatch(request, *args, **kwargs)

class DashboardView(LoginRequiredMixin, CurrentPageMixin, TemplateView):
    """Main dashboard view displaying system metrics and message management."""
    template_name = "webapp/dashboard.html"
    current_page = "dashboard"
    items_per_page = 20

    def get_context_data(self, **kwargs):
        logger.debug("Generating dashboard context data")
        context = super().get_context_data(**kwargs)
        messages = Message.objects.all()
        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(messages, self.items_per_page)
        page_obj = paginator.get_page(page_number)
        # Populate context with system metrics
        context.update({
            'messages': page_obj,
            'has_pagination': paginator.num_pages > 1,
            'end_index': page_obj.end_index(),
            "total_messages": messages.count(),
            "total_campaigns": Campaign.objects.filter(status="ACTIVE").count(),
            'total_contacts': Contact.objects.count(),
            "active_contacts": Contact.objects.filter(status="active").count(),
            "inactive_contacts": Contact.objects.filter(status="inactive").count(),
            'groups': ContactGroup.objects.all()[:30],
        })
        context.update(MessageMetricsManager.get_total_system_metrics())
        logger.debug("Dashboard context data generated successfully")
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle bulk message sending to groups."""
        group_id = request.POST.get('group')
        message_text = request.POST.get('message')
        
        if not message_text:
            logger.warning("Attempted to send message with empty text")
            return JsonResponse({
                'success': False,
                'message': 'Message text is required'
            }, status=400)

        try:
            if group_id == 'all':
                recipients = Contact.objects.filter(status='active')
                logger.info("Sending message to all active contacts")
            else:
                group = ContactGroup.objects.get(id=group_id)
                recipients = Contact.objects.filter(groups=group, status='active')
                logger.info(f"Sending message to group {group.name}")

            status = send_message(recipients, message_text)
            sms_logger.info(f"Bulk message queued for {recipients.count()} recipients")
            return JsonResponse({
                'success': True,
                'message': f'Message queued successfully for {recipients.count()} recipients!'
            })

        except ContactGroup.DoesNotExist:
            logger.error(f"Attempted to send message to non-existent group ID: {group_id}")
            return JsonResponse({
                'success': False,
                'message': 'Selected group does not exist'
            }, status=400)

class ContactView(LoginRequiredMixin, CurrentPageMixin, TemplateView):
    """View for managing contacts and contact groups."""
    template_name = "webapp/contacts.html"
    current_page = "contacts"
    items_per_page = 20

    def get_context_data(self, **kwargs):
        logger.debug("Generating contacts view context")
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get('search', '')
        contacts = Contact.objects.all()
        
        if search_query:
            logger.info(f"Searching contacts with query: {search_query}")
            contacts = contacts.filter(
                Q(full_name__icontains=search_query) |
                Q(email__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )

        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(contacts, self.items_per_page)
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'groups': ContactGroup.objects.all()[:30],
            'contacts': page_obj,
            'total_contacts': contacts.count(),
            "total_active_groups": ContactGroup.objects.count(),
            'start_index': page_obj.start_index(),
            'end_index': page_obj.end_index(),
            'has_pagination': paginator.num_pages > 1
        })
        context.update(MessageMetricsManager.get_total_system_metrics())
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle contact-related POST requests."""
        action = request.POST.get('action')
        logger.debug(f"Processing contact action: {action}")
        if action == 'toggle_status':
            return self.handle_status_toggle(request)
        elif action == "create_new_contact":
            return self.handle_create_contact(request)
        elif action == "import_contacts":
            return self.handle_import_contact(request)
        else:
            return self.handle_group_creation(request)
        
    @transaction.atomic
    def handle_import_contact(self, request):
        logger.info("Starting CSV import process")
        try:
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                logger.warning("CSV import attempted without file")
                return JsonResponse({
                    'success': False,
                    'message': 'No file uploaded'
                }, status=400)

            logger.debug(f"Processing CSV file: {csv_file.name}")
            file_content = csv_file.read().decode('utf-8')
            csv_data = StringIO(file_content)
            reader = csv.DictReader(csv_data)
            headers = reader.fieldnames

            logger.debug(f"CSV headers found: {headers}")
            required_fields = ['phone_number']
            
            if not headers:
                logger.error("Empty or invalid CSV file uploaded")
                return JsonResponse({
                    'success': False,
                    'message': 'CSV file is empty or invalid'
                }, status=400)

            missing_fields = [field for field in required_fields if field not in headers]
            if missing_fields:
                logger.warning(f"CSV missing required fields: {missing_fields}")
                return JsonResponse({
                    'success': False,
                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                }, status=400)

            success_count = 0
            error_count = 0
            errors = []
            
            logger.info("Starting to process CSV rows")
            for row_number, row in enumerate(reader, start=2):
                try:
                    # Extract and clean data
                    phone_number = re.sub(r'[\s\(\)\-_]*', "", row.get('phone_number', '').strip())
                    full_name = row.get('full_name', '').strip()
                    email = row.get('email', '').strip()
                    
                    if not phone_number:
                        logger.warning(f"Row {row_number}: Empty phone number")
                        errors.append(f'Row {row_number}: Phone number is required')
                        error_count += 1
                        continue

                    # Create or update contact
                    contact, created = Contact.objects.get_or_create(
                        phone_number=phone_number,
                        defaults={
                            'full_name': full_name,
                            'email': email
                        }
                    )

                    if created:
                        logger.debug(f"Created new contact: {phone_number}")
                        ContactMetrics.objects.create(contact=contact)
                    else:
                        logger.debug(f"Updated existing contact: {phone_number}")

                    # Handle group assignment
                    group_id = request.POST.get('group_id')
                    if group_id:
                        try:
                            group = ContactGroup.objects.get(id=group_id)
                            contact.groups.add(group)
                            logger.debug(f"Added contact {phone_number} to group {group.name}")
                        except ContactGroup.DoesNotExist:
                            logger.warning(f"Row {row_number}: Group {group_id} not found")
                            errors.append(f'Row {row_number}: Group not found')

                    success_count += 1

                except Exception as e:
                    logger.error(f"Error processing row {row_number}: {str(e)}", exc_info=True)
                    error_count += 1
                    errors.append(f'Row {row_number}: {str(e)}')

            # Prepare response message
            message = f'Successfully imported {success_count} contacts.'
            if error_count > 0:
                message += f' {error_count} errors occurred.'

            logger.info(f"CSV import completed. Successes: {success_count}, Errors: {error_count}")
            if errors:
                logger.warning(f"Import errors: {'; '.join(errors[:10])}")

            return JsonResponse({
                'success': True,
                'message': message,
                'details': {
                    'success_count': success_count,
                    'error_count': error_count,
                    'errors': errors[:10]
                }
            })

        except Exception as e:
            logger.error(f"Fatal error during CSV import: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error processing file: {str(e)}'
            }, status=400)
    @transaction.atomic 
    def handle_create_contact(self, request):
        """Create a new contact and associated metrics."""
        try:
            contact = Contact.objects.create(
                full_name=request.POST.get('full_name'),
                phone_number=request.POST.get('phone_number'),
                email=request.POST.get('email'),
            )
            
            ContactMetrics.objects.create(contact=contact)
            
            groups = request.POST.getlist('groups')
            if groups:
                contact.groups.set(groups)
            
            logger.info(f"Created new contact: {contact.full_name}")
            return JsonResponse({
                'success': True,
                'message': 'Contact created successfully!',
            })
        except Exception as e:
            logger.error(f"Error creating contact: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}',
            },status=400)
        
    @transaction.atomic
    def handle_status_toggle(self, request):
        """Toggle contact active/inactive status."""
        try:
            contact_id = request.POST.get('contact_id')
            new_status = "inactive" if request.POST.get('is_active') == "true" else "active"

            if not contact_id:
                logger.warning("Contact status toggle attempted without contact ID")
                return JsonResponse({
                    'success': False,
                    'message': 'Contact ID is required'
                }, status=400)

            contact = Contact.objects.get(id=contact_id)
            contact.status = new_status
            contact.save()
            
            logger.info(f"Contact {contact_id} status changed to {new_status}")
            return JsonResponse({
                'success': True,
                'message': f'Contact {"activated" if new_status == "active" else "deactivated"} successfully',
                'contact': {
                    'id': contact.id,
                    'is_active': contact.is_active,
                    'status_display': contact.status_display
                }
            })

        except Contact.DoesNotExist:
            logger.error(f"Attempted to toggle status for non-existent contact ID: {contact_id}")
            return JsonResponse({
                'success': False,
                'message': 'Contact not found'
            }, status=404)
        except Exception as e:
            logger.error(f"Error toggling contact status: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error updating contact status: {str(e)}'
            }, status=400)
        
    @transaction.atomic
    def handle_group_creation(self, request):
        """Create a new contact group."""
        try:
            name = request.POST.get('name')
            description = request.POST.get('description')
            color = request.POST.get('color')

            if not name:
                logger.warning("Attempted to create group without name")
                return JsonResponse({
                    'success': False,
                    'message': 'Group name is required'
                }, status=400)

            group = ContactGroup.objects.create(
                name=name,
                description=description,
                color=color,
                created_by=request.user
            )
            
            logger.info(f"Created new contact group: {name}")
            return JsonResponse({
                'success': True,
                'message': 'Group created successfully',
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'color': group.color,
                    'description': group.description
                }
            })

        except Exception as e:
            logger.error(f"Error creating contact group: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)

class CompaignView(LoginRequiredMixin, CurrentPageMixin, TemplateView):
    """View for managing SMS campaigns."""
    template_name = "webapp/campaigns.html"
    current_page = "campaigns"
    items_per_page = 20

    def get_context_data(self, **kwargs):
        logger.debug("Generating campaign view context")
        context = super().get_context_data(**kwargs)
        campaigns = Campaign.objects.all()
        page_number = self.request.GET.get('page', 1)
        paginator = Paginator(campaigns, self.items_per_page)
        page_obj = paginator.get_page(page_number)
        
        context.update({
            'campaigns': page_obj,
            "total_campaigns": campaigns.count(),
            'has_pagination': paginator.num_pages > 1,
            'end_index': page_obj.end_index(),
            "start_index": page_obj.start_index(),
            "groups": ContactGroup.objects.all()
        })
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle campaign-related POST requests."""
        action = request.POST.get('action')
        logger.debug(f"Processing campaign action: {action}")
        
        if action == "create_campaign":
            return self.handle_create_campaign(request)
        elif action == "send_campaign":
            return self.handle_send_campaign(request)
        return self.handle_toggle_status(request)
    
    def handle_toggle_status(self, request):
        """Toggle campaign active/cancelled status."""
        campaign_id = request.POST.get("campaign_id")
        status = request.POST.get("status")

        try:
            campaign = Campaign.objects.get(id=campaign_id)
            new_status = "ACTIVE" if status == "CANCELLED" else "CANCELLED"
            campaign.status = new_status
            campaign.save()
            
            logger.info(f"Campaign {campaign_id} status changed to {new_status}")
            return JsonResponse({
                "success": True,
                "message": f"Campaign is {campaign.status}!"
            })
        except ObjectDoesNotExist:
            logger.error(f"Attempted to toggle status for non-existent campaign ID: {campaign_id}")
            return JsonResponse({
                "success": False,
                "message": f"Campaign not found!"
            }, status=400)

    def handle_send_campaign(self, request):
        """Send campaign messages to recipients."""
        try:
            campaign_id = request.POST.get("campaign_id")
            campaign = Campaign.objects.get(id=campaign_id, status="ACTIVE")
            recipients = Contact.objects.filter(
                status="active",
                groups__in=campaign.groups.all()
            ).distinct()
            
            send_message(recipients, campaign.message)
            sms_logger.info(f"Campaign {campaign_id} sent to {recipients.count()} recipients")
            return JsonResponse({
                "success": True,
                "message": f"Campaign sent successfully to {recipients.count()} recipients!"
            })
        except ObjectDoesNotExist:
            logger.error(f"Attempted to send inactive or non-existent campaign: {campaign_id}")
            return JsonResponse({
                "success": False,
                "message": f"Campaign is not active!"
            }, status=400)

    @transaction.atomic
    def handle_create_campaign(self, request):
        """Create a new campaign."""
        try:
            campaign = Campaign.objects.create(
                name=request.POST.get("name"),
                campaign_type=request.POST.get("type"),
                message=request.POST.get("message"),
                created_by=request.user
            )
            
            groups = request.POST.getlist('groups')
            if groups:
                campaign.groups.set(groups)
            
            logger.info(f"Created new campaign: {campaign.name}")
            return JsonResponse({
                'success': True,
                'message': "Campaign Created Successfully"
            }, status=200)
        except Exception as e:
            logger.error(f"Error creating campaign: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error creating campaign status: {str(e)}'
            }, status=400)


class ConversationView(LoginRequiredMixin, CurrentPageMixin, TemplateView):
    """View for displaying conversation list."""
    template_name = "webapp/chats.html"
    current_page = "conversations"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_query = self.request.GET.get("search")

        # Get all active contacts
        contacts = Contact.objects.filter(status__iexact="ACTIVE")
        
        # Get the latest message for each contact using subquery
        latest_messages_subquery = Message.objects.filter(contact=OuterRef('contact')).order_by('-created_at')
        messages = Message.objects.filter(
            id=Subquery(
                latest_messages_subquery.values('id')[:1]
            )
        ).select_related('contact').order_by('-created_at')

        # Apply search filter if present
        if search_query:
            messages = messages.filter(
                Q(message__icontains=search_query) |
                Q(contact__phone_number__icontains=search_query) |
                Q(contact__full_name__icontains=search_query)
            )
            contacts = contacts.filter(
                Q(phone_number__icontains=search_query) |
                Q(full_name__icontains=search_query)
            )

        # Get contacts with no messages
        contacts_with_messages = messages.values_list('contact_id', flat=True)
        contacts_without_messages = contacts.exclude(id__in=contacts_with_messages)

        # Create dummy message objects for contacts without messages
        no_conversation_messages = []
        for contact in contacts_without_messages:
            no_conversation_messages.append({
                'contact': contact,
                'message': "No conversation yet",
                'created_at': contact.created_at,
                'is_dummy': True  # Flag to identify dummy messages in template
            })

        all_messages = list(messages)
        for dummy_msg in no_conversation_messages:
            all_messages.append(dummy_msg)

        context["messages"] = all_messages[:30]
        return context

class ConversationDetail(LoginRequiredMixin, TemplateView):
    """View for displaying individual conversation details."""
    template_name = "webapp/chat_detail.html"

    def get_context_data(self, **kwargs):
        logger.debug(f"Generating conversation detail for contact ID: {kwargs['pk']}")
        context = super().get_context_data(**kwargs)
        
        try:
            contact = Contact.objects.get(id=kwargs["pk"])
            messages = Message.objects.filter(contact=contact).order_by('created_at')
            
            context.update({
                "messages": messages,
                "contact": contact
            })
            logger.debug(f"Found {messages.count()} messages for contact {contact.full_name}")
            return context
        except Contact.DoesNotExist:
            logger.error(f"Attempted to view conversation for non-existent contact ID: {kwargs['pk']}")
            raise


    def post(self, request, *args, **kwargs):
        """Handle sending individual messages in a conversation."""
        try:
            message_text = request.POST.get("message")
            contact = Contact.objects.get(id=kwargs["pk"])
            
            if not message_text:
                logger.warning(f"Attempted to send empty message to contact {contact.id}")
                return JsonResponse({
                    'success': False,
                    'message': "Message text cannot be empty"
                }, status=400)

            send_message(contact, message_text)
            sms_logger.info(f"Sent message to contact {contact.id}: {message_text[:50]}...")
            
            return JsonResponse({
                'success': True,
                'message': "Message Delivered Successfully"
            }, status=200)
        except Contact.DoesNotExist:
            logger.error(f"Attempted to send message to non-existent contact ID: {kwargs['pk']}")
            return JsonResponse({
                'success': False,
                'message': "Contact not found"
            }, status=404)
        except Exception as e:
            logger.error(f"Error sending message to contact {kwargs['pk']}: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error sending message: {str(e)}'
            }, status=400)

@method_decorator(csrf_exempt, name='dispatch')
class ReceiveSMSView(View):
    """Handle incoming SMS messages from Twilio webhook."""
    
    def post(self, request, *args, **kwargs):
        from_number = request.POST.get('From')
        message_body = request.POST.get('Body')

        if not from_number or not message_body:
            sms_logger.error("Received invalid SMS webhook request - missing number or message")
            return HttpResponse("Invalid request", status=400)

        # Normalize phone number format
        if not from_number.startswith('+'):
            from_number = f"+1{from_number}"
            sms_logger.debug(f"Normalized phone number to: {from_number}")

        try:
            with transaction.atomic():
                # Get or create contact
                contact, created = Contact.objects.get_or_create(phone_number=from_number)
                if created:
                    logger.info(f"New contact created from incoming SMS: {from_number}")
                
                # Update metrics
                metrics, _ = ContactMetrics.objects.get_or_create(contact=contact)
                metrics.record_message_received()
                
                # Create message record
                Message.objects.create(
                    contact=contact,
                    message=message_body,
                    status="RECEIVED"
                )
                sms_logger.info(f"Successfully processed incoming SMS from {from_number}")

        except Exception as e:
            sms_logger.error(f"Error processing incoming SMS: {str(e)}", exc_info=True)
            return HttpResponse(f"Error: {e}", status=500)
        
        return HttpResponse("Message received", content_type="text/plain")