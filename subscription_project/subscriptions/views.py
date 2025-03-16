import os
import json
import base64
import requests
import logging
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from .models import MpesaTransaction, MpesaPayment, Voucher, UserConnection

# Set up logging for better debugging
logger = logging.getLogger(__name__)

def home(request):
    """ Renders the subscription options page with available plans. """
    subscription_plans = [
        {"validity": "2 Hours", "amount": 10},
        {"validity": "6 Hours", "amount": 15},
        {"validity": "12 Hours", "amount": 20},
        {"validity": "24 Hours", "amount": 30},
        {"validity": "2 Days", "amount": 50},
        {"validity": "3 Days", "amount": 80},
        {"validity": "1 Week", "amount": 190},
        {"validity": "2 Weeks", "amount": 350},
        {"validity": "1 Month", "amount": 600},
    ]
    return render(request, 'subscriptions/home.html', {"plans": subscription_plans})


@csrf_exempt  # Only use if testing without CSRF tokens
def upload_mpesa(request):
    """ Handles M-Pesa transaction verification via transaction code. """
    if request.method == "POST":
        mpesa_code = request.POST.get("mpesa_code", "").strip()

        if not mpesa_code:
            return JsonResponse({"success": False, "message": "M-Pesa code is required."}, status=400)

        try:
            payment = MpesaPayment.objects.get(transaction_code=mpesa_code)

            # Check if payment is within the valid timeframe (e.g., last 24 hours)
            if (now() - payment.timestamp).days > 1:
                return JsonResponse({"success": False, "message": "M-Pesa code has expired."}, status=400)

            return JsonResponse({"success": True, "message": "Payment verified. You are now connected."})

        except MpesaPayment.DoesNotExist:
            return JsonResponse({"success": False, "message": "Invalid M-Pesa code."}, status=400)

    return JsonResponse({"success": False, "message": "Invalid request method."}, status=405)


def redeem_voucher(request):
    """ Redeems a voucher and grants access to the user. """
    if request.method == "POST":
        voucher_code = request.POST.get("voucher_code")

        try:
            voucher = Voucher.objects.get(code=voucher_code)

            if voucher.is_used:
                return JsonResponse({"status": "error", "message": "This voucher has already been used!"})

            voucher.is_used = True
            voucher.save()

            reconnect_user(request.user)

            return JsonResponse({"status": "success", "message": "Voucher redeemed successfully. You are now connected!"})

        except Voucher.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Invalid voucher code!"})

    return JsonResponse({"status": "error", "message": "Invalid request"})


def login_view(request):
    """ Handles user authentication. """
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            messages.success(request, "Login successful!")
            return redirect("home")
        else:
            messages.error(request, "Invalid username or password.")
    return redirect("home")



logger = logging.getLogger(__name__)

def subscription_options(request):
    """ Processes subscription payments via M-Pesa. """
    if request.method == "POST":
        phone_number = request.POST.get("phone_number")
        amount = request.POST.get("subscription")

        if not phone_number.startswith(("07", "01")) or len(phone_number) != 10:
            messages.error(request, "Invalid phone number! Please enter a valid Safaricom number.")
            return redirect("home")

        messages.success(request, f"Subscription of Ksh {amount} activated for {phone_number}!")
        return redirect("home")


def format_phone_number(phone_number):
    """ Converts 07XXXXXXXX or 01XXXXXXXX to 2547XXXXXXXX or 2541XXXXXXXX for M-Pesa API compatibility. """
    if phone_number.startswith(("07", "01")):
        return f"254{phone_number[1:]}"
    return phone_number




def get_mpesa_access_token():
    """ Gets an access token from the Safaricom API. """
    url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"
    consumer_key = settings.MPESA_CONSUMER_KEY
    consumer_secret = settings.MPESA_CONSUMER_SECRET

    # Correct Authorization method
    credentials = f"{consumer_key}:{consumer_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {"Authorization": f"Basic {encoded_credentials}"}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get M-Pesa token: {e}")
        return None



def stk_push_request(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone_number = format_phone_number(data.get('phone_number', ''))
            amount = data.get('amount')

            if not phone_number or not amount:
                return JsonResponse({"success": False, "message": "Invalid phone number or amount."})

            access_token = get_mpesa_access_token()
            if not access_token:
                return JsonResponse({"success": False, "message": "Failed to get access token."})

            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
            business_short_code = settings.MPESA_SHORTCODE
            passkey = settings.MPESA_PASSKEY
            password = base64.b64encode(f"{business_short_code}{passkey}{timestamp}".encode()).decode()

            payload = {
                "BusinessShortCode": business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": amount,
                "PartyA": phone_number,
                "PartyB": business_short_code,
                "PhoneNumber": phone_number,
                "CallBackURL": settings.MPESA_CALLBACK_URL,
                "AccountReference": "Payment",
                "TransactionDesc": "Payment for goods/services"
            }

            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            stk_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"

            response = requests.post(stk_url, json=payload, headers=headers)
            response_data = response.json()

            if response.status_code == 200 and response_data.get("ResponseCode") == "0":
                return JsonResponse({
                    "success": True,
                    "message": "STK Push sent successfully.",
                    "CheckoutRequestID": response_data.get("CheckoutRequestID")
                })
            else:
                logger.error(f"STK Push Failed: {response_data}")
                return JsonResponse({"success": False, "message": response_data.get("errorMessage", "Failed to initiate payment.")})

        except Exception as e:
            logger.error(f"Error in STK Push: {e}")
            return JsonResponse({"success": False, "message": "Internal server error."})

    return JsonResponse({"success": False, "message": "Invalid request method."})


@csrf_exempt
def mpesa_callback(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            callback_data = data.get("Body", {}).get("stkCallback", {})

            result_code = callback_data.get("ResultCode")
            result_desc = callback_data.get("ResultDesc")

            if result_code == 0:
                metadata = {item["Name"]: item.get("Value") for item in callback_data.get("CallbackMetadata", {}).get("Item", [])}

                merchant_request_id = callback_data.get("MerchantRequestID")
                checkout_request_id = callback_data.get("CheckoutRequestID")
                amount = metadata.get("Amount")
                receipt_number = metadata.get("MpesaReceiptNumber")
                phone_number = metadata.get("PhoneNumber")

                # Save the payment details to the database
                from .models import Payment  # Import your Payment model
                Payment.objects.create(
                    phone_number=phone_number,
                    amount=amount,
                    receipt_number=receipt_number,
                    status="Success",
                    merchant_request_id=merchant_request_id,
                    checkout_request_id=checkout_request_id
                )

                return JsonResponse({"message": "Payment received successfully!"}, status=200)

            else:
                logger.warning(f"STK Payment failed: {result_desc}")
                return JsonResponse({"message": "Payment failed", "reason": result_desc}, status=400)

        except Exception as e:
            logger.error(f"Error in M-Pesa Callback: {e}")
            return JsonResponse({"message": "Internal server error."}, status=500)

    return JsonResponse({"message": "Invalid request"}, status=400)




def reconnect_user(user):
    """ Simulates reconnecting a user after voucher validation. """
    try:
        user_connection, created = UserConnection.objects.get_or_create(user=user)
        user_connection.is_connected = True
        user_connection.save()
    except Exception as e:
        logger.error(f"Error reconnecting user {user}: {e}")

    logger.info(f"User {user.username} reconnected successfully!")
