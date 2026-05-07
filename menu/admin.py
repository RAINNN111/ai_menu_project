from django.contrib import admin
from .models import Menu, Order, OrderItem
from .models import Menu, Flavor

admin.site.register(Menu)
admin.site.register(Order)
admin.site.register(OrderItem) 
admin.site.register(Flavor)