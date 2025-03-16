from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid
from datetime import timedelta


class MpesaPayment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_code = models.CharField(max_length=15, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.transaction_code} - {'Used' if self.used else 'Not Used'}"

SUBSCRIPTION_PLANS = {
    10: timedelta(hours=2),
    15: timedelta(hours=6),
    20: timedelta(hours=12),
    30: timedelta(days=1),
    50: timedelta(days=2),
    80: timedelta(days=3),
    190: timedelta(weeks=1),
    350: timedelta(weeks=2),
    600: timedelta(weeks=4),
}

class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    amount_paid = models.IntegerField()
    start_time = models.DateTimeField(auto_now_add=True)
    expiry_time = models.DateTimeField()

    def save(self, *args, **kwargs):
        if self.amount_paid in SUBSCRIPTION_PLANS:
            self.expiry_time = self.start_time + SUBSCRIPTION_PLANS[self.amount_paid]
        super().save(*args, **kwargs)

    def is_active(self):
        return timezone.now() < self.expiry_time

    def __str__(self):
        return f"{self.user.username} - {self.amount_paid} Ksh"

class Payment(models.Model):
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    receipt_number = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, default="Pending")
    merchant_request_id = models.CharField(max_length=100, unique=True)
    checkout_request_id = models.CharField(max_length=100, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.phone_number} - {self.amount} - {self.status}"

class Voucher(models.Model):
    code = models.CharField(max_length=50, unique=True)
    discount = models.IntegerField()
    is_used = models.BooleanField(default=False)

    def __str__(self):
        return self.code

class UserConnection(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    is_connected = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {'Connected' if self.is_connected else 'Disconnected'}"

class MpesaTransaction(models.Model):
    transaction_id = models.CharField(
        max_length=50, unique=True, null=True, blank=True, default=uuid.uuid4().hex
    )
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default="Pending")  # Added default value
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_id} - {self.phone_number}"
