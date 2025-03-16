from django.urls import path
from .views import home, upload_mpesa, redeem_voucher, login_view,stk_push_request, mpesa_callback, subscription_options

urlpatterns = [
    path("", home, name="home"),
    path("upload-mpesa/", upload_mpesa, name="upload_mpesa"),
    path("redeem-voucher/", redeem_voucher, name="redeem_voucher"),
    path("login/", login_view, name="login"),
    path("subscription-options/", subscription_options, name="subscription_options"),
    path("stk_push/", stk_push_request, name="stk_push_request"),
    path("mpesa_callback/", mpesa_callback, name="mpesa_callback"),

]
