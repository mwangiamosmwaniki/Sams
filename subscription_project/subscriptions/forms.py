from django import forms
from .models import Payment, Voucher

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['mpesa_code', 'amount']

class VoucherForm(forms.Form):
    code = forms.CharField(max_length=20, label="Enter Voucher Code")
