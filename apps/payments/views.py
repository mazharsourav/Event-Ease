from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.http import Http404, JsonResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
import requests
import hashlib
import logging
import uuid
from decimal import Decimal, InvalidOperation
from apps.events.models import EventBooking
from .models import Payment

logger = logging.getLogger(__name__)

@login_required
def payment_process(request, booking_id):
    """Process payment for a booking"""
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    # Check if booking is already paid
    if booking.payment_status == 'completed':
        messages.info(request, 'This booking has already been paid.')
        return redirect('events:event_detail', pk=booking.event.pk)
    
    # Check if booking amount is 0 (free event)
    if booking.amount == 0:
        booking.payment_status = 'completed'
        booking.status = 'confirmed'
        booking.save()
        messages.success(request, 'Registration confirmed for free event!')
        return redirect('events:event_detail', pk=booking.event.pk)
    
    # Get or create payment record
    payment, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'user': request.user,
            'amount': booking.amount,
            'payment_method': 'credit_card',
            'billing_name': booking.attendee_name,
            'billing_email': booking.attendee_email,
            'billing_phone': booking.attendee_phone,
        }
    )
    
    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'credit_card')
        
        # Route to specific payment forms for bKash and Nagad
        if payment_method == 'bkash':
            return redirect('payments:bkash_payment', booking_id=booking.id)
        elif payment_method == 'nagad':
            return redirect('payments:nagad_payment', booking_id=booking.id)
        # Route to SSL Commerz gateway for other payment methods
        elif payment_method in ['credit_card', 'ssl']:
            return initiate_ssl_payment_gateway(request, booking, payment, payment_method)
        
        # Simple mock payment processing for other methods
        elif payment_method in ['credit_card', 'debit_card', 'paypal']:
            # Simulate successful payment
            payment.payment_method = payment_method
            payment.transaction_id = f"TXN_{uuid.uuid4().hex[:12].upper()}"
            payment.payment_gateway = "mock_gateway"
            payment.mark_as_paid()
            
            messages.success(request, f'Payment successful! Your booking is confirmed. Transaction ID: {payment.transaction_id}')
            return redirect('events:event_detail', pk=booking.event.pk)
        else:
            messages.error(request, 'Invalid payment method selected.')
    
    context = {
        'booking': booking,
        'payment': payment,
        'event': booking.event,
        # Quick pay is a development shortcut; see quick_pay() below.
        'allow_quick_pay': settings.DEBUG,
    }

    return render(request, 'payments/payment_process.html', context)

@login_required
def payment_success(request, payment_id):
    """Payment success page"""
    payment = get_object_or_404(Payment, id=payment_id, user=request.user)
    
    context = {
        'payment': payment,
        'booking': payment.booking,
        'event': payment.booking.event,
    }
    
    return render(request, 'payments/payment_success.html', context)

@login_required
def payment_cancel(request, booking_id):
    """Payment cancelled page"""
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    context = {
        'booking': booking,
        'event': booking.event,
    }
    
    return render(request, 'payments/payment_cancel.html', context)

@login_required
@require_POST
def quick_pay(request, booking_id):
    """Mark a booking paid without a gateway. Development only.

    It exists so the booking flow can be demonstrated without real bKash, Nagad or card
    credentials. Taking money is the one thing a demo shortcut must never do in production,
    so outside DEBUG this endpoint does not exist at all.
    """
    if not settings.DEBUG:
        raise Http404('Quick pay is only available in development.')

    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)

    if booking.payment_status == 'completed':
        return JsonResponse({'success': False, 'message': 'Already paid'})
    
    # Get or create payment
    payment, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'user': request.user,
            'amount': booking.amount,
            'payment_method': 'cash',
            'billing_name': booking.attendee_name,
            'billing_email': booking.attendee_email,
            'billing_phone': booking.attendee_phone,
        }
    )
    
    # Mark as paid
    payment.payment_method = 'cash'
    payment.transaction_id = f"QUICK_{uuid.uuid4().hex[:8].upper()}"
    payment.payment_gateway = "manual"
    payment.mark_as_paid()
    
    return JsonResponse({
        'success': True, 
        'message': f'Payment completed! Transaction ID: {payment.transaction_id}'
    })


def _amount_matches(reported, expected):
    """True when the gateway says it took at least what the booking costs."""
    try:
        return Decimal(str(reported)) >= Decimal(expected)
    except (InvalidOperation, TypeError):
        return False


# SSL Commerz Gateway Integration Functions

def initiate_ssl_payment_gateway(request, booking, payment, preferred_method=None):
    """Initiate SSL Commerz payment gateway with all payment options"""
    
    # Generate unique transaction ID
    tran_id = f"SSL_{uuid.uuid4().hex[:12].upper()}"
    
    # Payment data for SSL Commerz gateway
    payment_data = {
        'store_id': settings.SSLCOMMERZ_STORE_ID,
        'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
        'total_amount': str(booking.amount),
        'currency': 'BDT',
        'tran_id': tran_id,
        'success_url': request.build_absolute_uri(reverse('payments:ssl_success')),
        'fail_url': request.build_absolute_uri(reverse('payments:ssl_fail')),
        'cancel_url': request.build_absolute_uri(reverse('payments:ssl_cancel')),
        'ipn_url': request.build_absolute_uri(reverse('payments:ssl_ipn')),
        
        # Product details
        'product_name': f"Event Booking - {booking.event.title}",
        'product_category': 'Event Tickets',
        'product_profile': 'general',
        'num_of_item': '1',
        
        # Customer details
        'cus_name': booking.attendee_name,
        'cus_email': booking.attendee_email,
        'cus_add1': 'N/A',
        'cus_city': 'Dhaka',
        'cus_state': 'Dhaka',
        'cus_postcode': '1000',
        'cus_country': 'Bangladesh',
        'cus_phone': booking.attendee_phone or '01700000000',
        'cus_fax': '',
        
        # Shipping details
        'ship_name': booking.attendee_name,
        'ship_add1': 'N/A',
        'ship_city': 'Dhaka',
        'ship_state': 'Dhaka',
        'ship_postcode': '1000',
        'ship_country': 'Bangladesh',
        'shipping_method': 'NO',
        
        # Store reference data
        'value_a': str(booking.id),
        'value_b': str(payment.id),
        'value_c': preferred_method or 'all',  # Store preferred method for reference
    }
    
    # Update payment record
    payment.transaction_id = tran_id
    payment.payment_method = preferred_method or 'ssl'
    payment.payment_gateway = 'sslcommerz'
    payment.payment_status = 'pending'
    payment.save()
    
    try:
        # Make request to SSL Commerz
        logger.info('Opening an SSLCommerz session for booking %s (%s)', booking.id, tran_id)
        response = requests.post(settings.SSLCOMMERZ_INIT_URL, data=payment_data, timeout=30)
        
        response_data = response.json()
        
        if response_data.get('status') == 'SUCCESS':
            # Redirect to SSL Commerz gateway page with all payment options
            gateway_url = response_data.get('GatewayPageURL')
            return redirect(gateway_url)
        else:
            error_message = response_data.get('failedreason', 'Unknown error')
            logger.warning('SSLCommerz refused a session for %s: %s', tran_id, error_message)
            messages.error(request, f"Payment initialization failed: {error_message}")
            return redirect('payments:payment_process', booking_id=booking.id)
            
    except Exception as e:
        logger.exception('Could not reach SSLCommerz for %s', tran_id)
        messages.error(request, f"Payment gateway error: {str(e)}")
        return redirect('payments:payment_process', booking_id=booking.id)


@csrf_exempt
def ssl_success(request):
    """Handle SSL Commerz success callback"""
    if request.method == 'POST':
        val_id = request.POST.get('val_id')
        tran_id = request.POST.get('tran_id')
        amount = request.POST.get('amount')
        currency = request.POST.get('currency')
        store_amount = request.POST.get('store_amount')
        bank_tran_id = request.POST.get('bank_tran_id')
        status = request.POST.get('status')
        
        # Validate transaction with SSL Commerz
        validation_data = {
            'val_id': val_id,
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'format': 'json'
        }
        
        try:
            validation_response = requests.get(settings.SSLCOMMERZ_VALIDATION_URL, params=validation_data)
            validation_result = validation_response.json()
            
            if validation_result.get('status') == 'VALID':
                # Find payment by transaction ID
                try:
                    payment = Payment.objects.get(transaction_id=tran_id)
                    booking = payment.booking
                    
                    if not _amount_matches(validation_result.get('amount'), payment.amount):
                        logger.error('SSLCommerz reported %s for %s, which should be %s',
                                     validation_result.get('amount'), tran_id, payment.amount)
                        messages.error(request, 'The amount paid did not match this booking.')
                        return redirect('payments:payment_process', booking_id=booking.id)

                    payment.bank_transaction_id = bank_tran_id
                    payment.gateway_response = validation_result
                    payment.mark_as_paid()
                    
                    messages.success(request, f'Payment successful! Transaction ID: {bank_tran_id}')
                    return redirect('events:event_detail', pk=booking.event.pk)
                    
                except Payment.DoesNotExist:
                    messages.error(request, 'Payment record not found.')
                    return redirect('events:event_list')
            else:
                messages.error(request, 'Payment validation failed.')
                return redirect('events:event_list')
                
        except Exception as e:
            messages.error(request, f'Payment validation error: {str(e)}')
            return redirect('events:event_list')
    
    return redirect('events:event_list')


@csrf_exempt  
def ssl_fail(request):
    """Handle SSL Commerz failure callback"""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        
        try:
            payment = Payment.objects.get(transaction_id=tran_id)
            payment.mark_as_failed('The gateway reported the payment as failed.')
            
            messages.error(request, 'Payment failed. Please try again.')
            return redirect('payments:payment_process', booking_id=payment.booking.id)
            
        except Payment.DoesNotExist:
            messages.error(request, 'Payment record not found.')
            
    return redirect('events:event_list')


@csrf_exempt
def ssl_cancel(request):
    """Handle SSL Commerz cancel callback"""
    if request.method == 'POST':
        tran_id = request.POST.get('tran_id')
        
        try:
            # Nothing is written: the person backed out of the gateway and may try again,
            # so the payment stays pending and the booking keeps its place.
            payment = Payment.objects.get(transaction_id=tran_id)
            
            messages.info(request, 'Payment was cancelled.')
            return redirect('payments:payment_process', booking_id=payment.booking.id)
            
        except Payment.DoesNotExist:
            messages.error(request, 'Payment record not found.')
            
    return redirect('events:event_list')


@csrf_exempt
def ssl_ipn(request):
    """Handle SSL Commerz IPN (Instant Payment Notification)"""
    if request.method == 'POST':
        val_id = request.POST.get('val_id')
        tran_id = request.POST.get('tran_id')
        
        # Validate IPN with SSL Commerz
        validation_data = {
            'val_id': val_id,
            'store_id': settings.SSLCOMMERZ_STORE_ID,
            'store_passwd': settings.SSLCOMMERZ_STORE_PASSWORD,
            'format': 'json'
        }
        
        try:
            validation_response = requests.get(settings.SSLCOMMERZ_VALIDATION_URL, params=validation_data)
            validation_result = validation_response.json()
            
            if validation_result.get('status') == 'VALID':
                payment = Payment.objects.get(transaction_id=tran_id)
                if payment.payment_status != 'completed' and _amount_matches(
                        validation_result.get('amount'), payment.amount):
                    payment.gateway_response = validation_result
                    payment.mark_as_paid()
                    
        except Exception:
            # The gateway retries an IPN it gets no answer to, so this is logged, not raised.
            logger.exception('Could not handle the IPN for %s', tran_id)
            
    return JsonResponse({'status': 'ok'})


# Dedicated bKash and Nagad Payment Views

@login_required
def bkash_payment(request, booking_id):
    """bKash payment form"""
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    # Check if booking is already paid
    if booking.payment_status == 'completed':
        messages.info(request, 'This booking has already been paid.')
        return redirect('events:event_detail', pk=booking.event.pk)
    
    # Get or create payment record
    payment, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'user': request.user,
            'amount': booking.amount,
            'payment_method': 'bkash',
            'billing_name': booking.attendee_name,
            'billing_email': booking.attendee_email,
            'billing_phone': booking.attendee_phone,
        }
    )
    
    context = {
        'booking': booking,
        'payment': payment,
        'event': booking.event,
    }
    
    return render(request, 'payments/bkash_payment.html', context)


@login_required
def bkash_process(request, booking_id):
    """Process bKash payment"""
    if request.method != 'POST':
        return redirect('payments:bkash_payment', booking_id=booking_id)
    
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    # Get payment details from form
    mobile = request.POST.get('mobile', '')
    pin = request.POST.get('pin', '')
    bkash_method = request.POST.get('bkash_method', 'wallet')
    
    # Validate mobile number
    if not mobile or len(mobile) != 10 or not mobile.startswith('1'):
        messages.error(request, 'Please enter a valid mobile number starting with 1')
        return redirect('payments:bkash_payment', booking_id=booking_id)
    
    # Validate PIN for wallet method
    if bkash_method == 'wallet' and (not pin or len(pin) != 5):
        messages.error(request, 'Please enter your 5-digit bKash PIN')
        return redirect('payments:bkash_payment', booking_id=booking_id)
    
    # Get or update payment record
    try:
        payment = Payment.objects.get(booking=booking)
        payment.payment_method = 'bkash'
        # Store the mobile number for SSL gateway
        payment.billing_phone = f"880{mobile}"  # Add country code
        payment.save()
    except Payment.DoesNotExist:
        payment = Payment.objects.create(
            booking=booking,
            user=request.user,
            amount=booking.amount,
            payment_method='bkash',
            billing_name=booking.attendee_name,
            billing_email=booking.attendee_email,
            billing_phone=f"880{mobile}",  # Add country code
        )
    
    # Store PIN temporarily in session for SSL gateway (if needed)
    request.session['bkash_pin'] = pin
    request.session['bkash_mobile'] = mobile
    
    # Redirect to SSL Commerz gateway with bKash preference and user data
    return initiate_ssl_payment_gateway(request, booking, payment, 'bkash')


@login_required
def nagad_payment(request, booking_id):
    """Nagad payment form"""
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    # Check if booking is already paid
    if booking.payment_status == 'completed':
        messages.info(request, 'This booking has already been paid.')
        return redirect('events:event_detail', pk=booking.event.pk)
    
    # Get or create payment record
    payment, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'user': request.user,
            'amount': booking.amount,
            'payment_method': 'nagad',
            'billing_name': booking.attendee_name,
            'billing_email': booking.attendee_email,
            'billing_phone': booking.attendee_phone,
        }
    )
    
    context = {
        'booking': booking,
        'payment': payment,
        'event': booking.event,
    }
    
    return render(request, 'payments/nagad_payment.html', context)


@login_required
def nagad_process(request, booking_id):
    """Process Nagad payment"""
    if request.method != 'POST':
        return redirect('payments:nagad_payment', booking_id=booking_id)
    
    booking = get_object_or_404(EventBooking, id=booking_id, user=request.user)
    
    # Get payment details from form
    mobile = request.POST.get('mobile', '')
    pin = request.POST.get('pin', '')
    nagad_method = request.POST.get('nagad_method', 'account')
    terms = request.POST.get('terms', '')
    
    # Validate mobile number
    if not mobile or len(mobile) != 10 or not mobile.startswith('1'):
        messages.error(request, 'Please enter a valid mobile number starting with 1')
        return redirect('payments:nagad_payment', booking_id=booking_id)
    
    # Validate PIN for account method
    if nagad_method == 'account' and (not pin or len(pin) != 6):
        messages.error(request, 'Please enter your 6-digit Nagad PIN')
        return redirect('payments:nagad_payment', booking_id=booking_id)
    
    # Validate terms acceptance
    if not terms:
        messages.error(request, 'Please accept the Terms & Conditions to proceed')
        return redirect('payments:nagad_payment', booking_id=booking_id)
    
    # Get or update payment record
    try:
        payment = Payment.objects.get(booking=booking)
        payment.payment_method = 'nagad'
        # Store the mobile number for SSL gateway
        payment.billing_phone = f"880{mobile}"  # Add country code
        payment.save()
    except Payment.DoesNotExist:
        payment = Payment.objects.create(
            booking=booking,
            user=request.user,
            amount=booking.amount,
            payment_method='nagad',
            billing_name=booking.attendee_name,
            billing_email=booking.attendee_email,
            billing_phone=f"880{mobile}",  # Add country code
        )
    
    # Store PIN temporarily in session for SSL gateway (if needed)
    request.session['nagad_pin'] = pin
    request.session['nagad_mobile'] = mobile
    
    # Redirect to SSL Commerz gateway with Nagad preference and user data
    return initiate_ssl_payment_gateway(request, booking, payment, 'nagad')
