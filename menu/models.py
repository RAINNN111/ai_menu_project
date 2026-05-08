from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone
from django.contrib.auth.models import User


class Coupon(models.Model):
    STATUS_CHOICES = [
        ("unused", "未使用"),
        ("used", "已使用"),
        ("expired", "已过期"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.ForeignKey("Order", on_delete=models.CASCADE, null=True, blank=True)

    code = models.CharField(max_length=50, unique=True)
    amount = models.IntegerField(default=0)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="unused")

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)   # ⭐新增
    
    def is_valid(self):
        return self.status == "unused" and self.expires_at > timezone.now()


class Favorite(models.Model):
    menu_name = models.CharField(max_length=100)
    image_url = models.URLField()
    total = models.IntegerField(default=1)

    def __str__(self):
        return self.menu_name

class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    cake_name = models.CharField(max_length=200, null=True, blank=True)

    flavor = models.CharField(max_length=100, default="unknown")
    image_url = models.URLField(default="")
    status = models.CharField(max_length=20, default="pending")
    order_type = models.CharField(max_length=20, default="menu")

    layers = models.IntegerField(null=True, blank=True)
    size = models.IntegerField(null=True, blank=True)

    reserved_date = models.DateField(null=True, blank=True)
    reserved_time = models.TimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    price = models.IntegerField(default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.all())

class AIOrder(models.Model):
    order = models.OneToOneField("Order", on_delete=models.CASCADE)
    prompt = models.TextField()
    ai_model = models.CharField(max_length=50)
    result_image = models.URLField()

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    menu = models.ForeignKey("Menu", on_delete=models.CASCADE)
    quantity = models.IntegerField()

    @property
    def total_price(self):
        return self.menu.price * self.quantity


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    menu = models.ForeignKey("Menu", on_delete=models.CASCADE)
    quantity = models.IntegerField(default=1)

class Flavor(models.Model):
    name = models.CharField(max_length=50)

    def __str__(self):
        return self.name

class Menu(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    price = models.DecimalField(max_digits=6, decimal_places=2)
    image = models.ImageField(upload_to='menu_images/', null=True, blank=True)
    tags = models.CharField(max_length=200)
    flavors = models.ManyToManyField(Flavor)

    def __str__(self):
        return self.name
    
class UserPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    preferred_flavors = models.ManyToManyField(Flavor, blank=True)