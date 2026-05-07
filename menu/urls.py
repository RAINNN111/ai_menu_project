from django.urls import path
from .views import login_view, menu_list, menu_detail
from .views import add_to_cart
from .views import cart_view
# from .views import ai_upload
from .views import register
from .views import profile
from . import views
from django.conf import settings
from django.conf.urls.static import static
from .views import generate_cake
from .views import confirm_order
from .views import logout_confirm
from .views import logout_do


urlpatterns = [
    path("login/", login_view),
    path("menu/", menu_list),
    path("menu/<int:menu_id>/", menu_detail),
    path("cart/add/", add_to_cart),
    path("cart/", cart_view),
    # path("ai/", ai_upload), 
    path("register/", register),
    path("cart/update/", views.cart_update),
    path("cart/delete/", views.cart_delete),
    path("profile/", profile),
    path("logout/", logout_confirm),
    path("logout/do/", logout_do),
    path('cart/checkout/', views.checkout, name='checkout'),
    path("order/<int:order_id>/", views.order_detail),
    path("customize/", views.customize, name="customize"),
    path("api/cake/", generate_cake),
    path("api/order/confirm/", confirm_order),
    path("api/ai-order/<int:id>/", views.ai_order_detail),
    path("cart/apply-coupon/", views.apply_coupon, name="apply_coupon"),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)