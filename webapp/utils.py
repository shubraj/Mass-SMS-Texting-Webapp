from .models import ContactMetrics, Message
from django.db import transaction
from django.conf import settings
from twilio.rest import Client
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

# Initialize loggers
logger = logging.getLogger('webapp')
sms_logger = logging.getLogger('webapp.sms')

# Initialize Twilio client
client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def get_message_status(message_sid):
    """
    Fetch the current status of a message from Twilio API.
    """
    try:
        sms_logger.debug(f"Fetching status for message SID: {message_sid}")
        message = client.messages(message_sid).fetch()
        sms_logger.debug(f"Message {message_sid} status: {message.status}")
        return message.status
    except Exception as e:
        sms_logger.error(f"Failed to fetch message status for SID {message_sid}: {str(e)}")
        return None

@transaction.atomic
def send_message_to_recipient(recipient, message):
    """
    Send a single SMS message to a recipient using Twilio.
    """
    try:
        sms_logger.info(f"Sending message to {recipient.phone_number}")
        
        # Send the message via Twilio API
        twilio_message = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=recipient.phone_number
        )
        
        sms_logger.debug(f"Twilio message created with SID: {twilio_message.sid}")
        
        # Check message status
        status = get_message_status(twilio_message.sid)

        if status == "undelivered":
            status = "failed"

        if status != "failed":
            status = "delivered"
            sms_logger.info(f"Message delivered to {recipient.phone_number}")
        else:
            sms_logger.warning(f"Message to {recipient.phone_number} marked as failed by Twilio")
            
        # Save the message status
        Message.objects.create(
            contact=recipient,
            message=message,
            status=status.upper()
        )

        # Record metrics for the contact
        contact_metrics, created = ContactMetrics.objects.get_or_create(contact=recipient)
        if created:
            logger.debug(f"Created new contact metrics for {recipient.phone_number}")
        if status == "failed":
            contact_metrics.record_message_failed()
            return False
        else:
            contact_metrics.record_message_sent()
        return True

    except Exception as e:
        sms_logger.error(
            f"Failed to send message to {recipient.phone_number}: {str(e)}",
            exc_info=True
        )
        return False

def send_message(recipients, message):
    """
    Send messages to multiple recipients in parallel using ThreadPoolExecutor.
    """
    # Convert single recipient to list if necessary
    if not hasattr(recipients, "__iter__"):
        recipients = [recipients]
        sms_logger.debug("Converting single recipient to list")

    total_recipients = len(recipients)
    sms_logger.info(f"Starting bulk message send to {total_recipients} recipients")

    success_count = 0
    failure_count = 0

    # Use ThreadPoolExecutor for parallel sending
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        futures = []
        for recipient in recipients:
            futures.append(
                executor.submit(send_message_to_recipient, recipient, message)
            )

        # Process results as they complete
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as e:
                failure_count += 1
                sms_logger.error(f"Executor task failed: {str(e)}", exc_info=True)

    # Log final results
    sms_logger.info(
        f"Bulk message send completed. "
        f"Successful: {success_count}, "
        f"Failed: {failure_count}, "
        f"Total: {total_recipients}"
    )

    return True