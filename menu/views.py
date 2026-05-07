from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
import base64
from django.contrib.auth.models import User
from django.http import JsonResponse
import json
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from .models import Menu, Order, OrderItem, Favorite,AIOrder
from django.views.decorators.csrf import csrf_exempt
import uuid
from datetime import timedelta
from django.utils import timezone
from .models import Coupon
from decimal import Decimal
from .models import Order, OrderItem, Menu, Coupon, AIOrder
from django.db.models import Count
from .models import Menu, Order, OrderItem
from django.db.models import Sum
from .models import Menu, OrderItem
import time
import requests
from django.utils.timezone import localtime
from django.contrib.auth import logout
from django.shortcuts import redirect
from .models import Flavor
from .models import Order, AIOrder, Favorite
from django.conf import settings 

def bind_coupon(request):

    data = json.loads(request.body)
    code = data.get("code")

    try:
        coupon = Coupon.objects.get(code=code)

        if coupon.user is not None:
            return JsonResponse({"success": False, "message": "使用済みです"})

        coupon.user = request.user
        coupon.save()

        return JsonResponse({"success": True})

    except Coupon.DoesNotExist:
        return JsonResponse({"success": False, "message": "存在しません"})


def get_cart_total(cart):

    total = Decimal("0")

    for menu_id, quantity in cart.items():

        menu = Menu.objects.get(id=int(menu_id))
        total += menu.price * Decimal(quantity)

    return total


def apply_coupon(request):

    data = json.loads(request.body)
    coupon_id = data.get("coupon_id")

    cart = request.session.get("cart", {})

    # ===== 计算 total =====
    total = 0
    for m_id, qty in cart.items():
        menu = Menu.objects.get(id=m_id)
        total += menu.price * qty

    discount = 0

    # ⭐关键：处理取消优惠券
    if coupon_id not in [None, "", "none", "null"]:

        coupon = Coupon.objects.get(id=coupon_id)

        # ⭐标记为已使用（关键）
        coupon.is_used = True
        coupon.save()

        request.session["coupon_id"] = coupon_id

        discount = min(coupon.amount, total)

    else:
        request.session["coupon_id"] = coupon_id

        try:
            coupon = Coupon.objects.get(id=coupon_id)
            discount = min(coupon.amount, total)
        except Coupon.DoesNotExist:
            discount = 0

    final = total - discount

    return JsonResponse({
        "success": True,
        "total": total,
        "discount": discount,
        "final": final
    })


def generate_coupon(order):

    amount = int(order.price * Decimal("0.1"))

    if amount <= 0:
        return

    Coupon.objects.create(
        user=order.user,
        order=order,
        code=str(uuid.uuid4()).replace("-", "")[:10].upper(),
        amount=amount,
        expires_at=timezone.now() + timedelta(days=365)
    )

def ai_order_detail(request, id):
    ai = AIOrder.objects.select_related("order").get(id=id)

    order = ai.order
    print("AI ID =", ai.id)
    print("ORDER ID =", order.id)
    print("PRICE =", order.price)

    return JsonResponse({
        "cake_name": order.cake_name,
        "flavor": order.flavor,
        "layers": order.layers,
        "size": order.size,
        "username": order.user.username,
        "reserved_date": order.reserved_date,
        "reserved_time": order.reserved_time,
        "created_at": localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
        "image": ai.result_image,
        "price": order.price   
    })

@login_required
def create_ai_order(request):
    if request.method == "POST":

        prompt = request.POST.get("prompt")
        ai_model = request.POST.get("ai_model")
        result_image = request.POST.get("result_image")

         # ⭐价格
        price = request.POST.get("price")

        # 1️⃣ Order
        order = Order.objects.create(
            user=request.user,
            flavor="AI Cake",
            image_url=result_image,
            status="done",
            order_type="ai",
            price=price
        )

        # 2️⃣ AIOrder
        AIOrder.objects.create(
            order=order,
            prompt=prompt,
            ai_model=ai_model,
            result_image=result_image
        )

        return JsonResponse({"success": True})

@csrf_exempt
@login_required
def confirm_order(request):

    if request.method == "POST":

        data = json.loads(request.body)
        cart = request.session.get("cart", {})

        total = Decimal("0")

        # ======================
        # 1️⃣ 先创建 Order
        # ======================
        order = Order.objects.create(
            user=request.user,
            cake_name=data.get("cake_name"),
            flavor=data.get("flavor"),
            image_url=data.get("image_url"),
            status="done",
            order_type="ai",
            layers=data.get("layers"),
            size=data.get("size"),
            reserved_date=data.get("reserved_date"),
            reserved_time=data.get("reserved_time"),
            price=0  # 先占位
        )

        # ======================
        # 2️⃣ 创建 OrderItem + 计算 total
        # ======================
        for m_id, qty in cart.items():
            menu = Menu.objects.get(id=m_id)

            total += menu.price * Decimal(qty)

            OrderItem.objects.create(
                order=order,
                menu=menu,
                quantity=qty
            )

        # ======================
        # 3️⃣ coupon
        # ======================
        coupon_id = request.session.get("coupon_id")
        discount = Decimal("0")

        if coupon_id:
            try:
                coupon = Coupon.objects.get(id=coupon_id)

                discount = min(coupon.amount, total)

                coupon.is_used = True
                coupon.save()

                request.session.pop("coupon_id", None)

            except:
                pass

        final_price = Decimal(str(data.get("price", 0))) - discount

        # ======================
        # 4️⃣ 更新 Order price
        # ======================
        order.price = final_price
        order.save()

        # ======================
        # 5️⃣ AIOrder
        # ======================
        AIOrder.objects.create(
            order=order,
            prompt=data.get("prompt", ""),
            ai_model=data.get("ai_model", "unknown"),
            result_image=data.get("image_url")
        )

        return JsonResponse({
            "message": "OK",
            "id": order.id
        })

def home(request):
    favorites = Favorite.objects.all().order_by("-id")
    return render(request, "home.html", {"favorites": favorites})


token = settings.REPLICATE_API_TOKEN

@csrf_exempt
def generate_cake(request):

    if request.method != "POST":
        return JsonResponse({"error": "only POST allowed"}, status=405)

    try:
        data = json.loads(request.body)

        flavor = data.get("flavor")
        layers = data.get("layers")
        size = data.get("size")

        prompt = f"""
        cute cartoon cake illustration, kawaii style,
        pastel colors, soft lighting,
        {flavor} cake, {layers} layers, {size},
        NOT realistic
        """

        response = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={
                "Authorization": f"Token {token}",
                "Content-Type": "application/json"
            },
            json={
                "version": "7762fd07cf82c948538e41f63f77d685e02b063e37e496e96eefd46c929f9bdc",
                "input": {"prompt": prompt}
            }
        )

        result = response.json()

        if response.status_code != 201:
            return JsonResponse({"error": result})

        get_url = result["urls"]["get"]

        while True:

            r = requests.get(
                get_url,
                headers={"Authorization": f"Token {token}"}
            )

            output = r.json()

            if output["status"] == "succeeded":

                image_url = output["output"][0]

                # ✅ 只返回结果，不存任何数据
                return JsonResponse({
                    "image_url": image_url,
                    "flavor": flavor,
                    "layers": layers,
                    "size": size
                })

            if output["status"] == "failed":
                return JsonResponse({"error": "AI生成に失敗しました"})

            time.sleep(2)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    

def customize(request):
    return render(request, "customize.html")

@login_required
def order_detail(request, order_id):

    order = Order.objects.get(id=order_id, user=request.user)
    items = order.items.all()

    # ===== 重新计算 total =====
    total = Decimal("0")

    for i in items:
        total += i.menu.price * Decimal(i.quantity)
    
    data = {
        "id": order.id,
        "created_at": localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
        "total": float(total),
        "discount": float(order.discount),   # 
        "final": float(order.price),         # 
        "items": [
            {
                "name": i.menu.name,
                "image": i.menu.image.url if i.menu.image else "",
                "quantity": i.quantity,
                "price": float(i.menu.price),
                "subtotal": float(i.menu.price * i.quantity),
            }
            for i in items
        ]
    }

    return JsonResponse(data)

@login_required
def profile(request):

    orders = Order.objects.filter(
        user=request.user,
        order_type="menu"
    ).order_by("-created_at")

    ai_orders = AIOrder.objects.select_related("order").filter(
        order__user=request.user
    ).order_by("-order__created_at")

    coupons = Coupon.objects.filter(
        user=request.user
    ).order_by("-id")
    return render(request, "profile.html", {
        "orders": orders,
        "ai_orders": ai_orders,
        "coupons": coupons
    })


# @login_required
def checkout(request):

    cart = request.session.get("cart", {})
    user = request.user

    if not cart:
        return redirect("/cart/")

    # 1️⃣ 创建订单
    order = Order.objects.create(user=user)

    # 2️⃣ 计算 total
    total = Decimal("0")

    for menu_id, quantity in cart.items():
        menu = Menu.objects.get(id=int(menu_id))
        quantity = int(quantity)

        OrderItem.objects.create(
            order=order,
            menu=menu,
            quantity=quantity
        )

        total += menu.price * Decimal(quantity)

    # ===== ⭐必须在循环外！！！ =====
    coupon_id = request.session.get("coupon_id")

    discount = Decimal("0")

    if coupon_id:
        try:
            coupon = Coupon.objects.get(id=coupon_id)

            # ⭐计算折扣
            discount = min(coupon.amount, total)

            # ⭐标记已使用
            coupon.is_used = True
            coupon.save()

            # ⭐清session
            request.session.pop("coupon_id", None)

        except:
            pass

    final_price = total - discount

    # ⭐保存两个值（关键🔥）
    order.price = final_price
    order.discount = discount   # ⭐新增（必须有这个字段）
    order.save()

    # 5️⃣ 生成优惠券
    generate_coupon(order)

    # 6️⃣ 清空购物车
    request.session["cart"] = {}

    return JsonResponse({
    "success": True,
    "coupon_created": True,
    "coupon_amount": float(total * Decimal("0.1"))
})

@login_required
def logout_confirm(request):
    return render(request, "logout.html")
@login_required
def logout_do(request):
    logout(request)
    return redirect("/login/")

@csrf_exempt
def cart_update(request):

    data = json.loads(request.body)

    menu_id = str(data.get("id"))
    quantity = int(data.get("quantity"))

    cart = request.session.get("cart", {})

    cart[menu_id] = quantity

    request.session["cart"] = cart

    total = 0
    for mid, qty in cart.items():
        menu = Menu.objects.get(id=mid)
        total += menu.price * qty

    return JsonResponse({"success": True, "total": float(total)})


# ================= DELETE =================
@csrf_exempt
def cart_delete(request):

    data = json.loads(request.body)
    menu_id = str(data.get("id"))

    cart = request.session.get("cart", {})

    if menu_id in cart:
        del cart[menu_id]

    request.session["cart"] = cart

    total = 0
    for mid, qty in cart.items():
        menu = Menu.objects.get(id=mid)
        total += menu.price * qty

    return JsonResponse({"success": True, "total": float(total)})

def register(request):
    if request.method == "POST":
        data = json.loads(request.body)

        username = data.get("username")
        password = data.get("password")
        flavors = data.get("flavors", [])

        if User.objects.filter(username=username).exists():
            return JsonResponse({"error": "ユーザー名は既に存在します"})

        user = User.objects.create_user(
            username=username,
            password=password
        )

        # ⭐⭐⭐ 核心：保存 flavor
        for f in flavors:
            flavor_obj, _ = Flavor.objects.get_or_create(name=f)
            user.preferred_flavors.add(flavor_obj)

        user.save()

        return JsonResponse({"status": "登録成功"})

# client = OpenAI()

# def ai_upload(request):
#     if request.method == "POST":
#         image_file = request.FILES.get("image")

#         # 转 base64
#         image_bytes = image_file.read()
#         image_base64 = base64.b64encode(image_bytes).decode("utf-8")

#         response = client.chat.completions.create(
#             model="gpt-4o-mini",
#             messages=[
#                 {
#                     "role": "user",
#                     "content": [
#                         {"type": "text", "text": "这是什么食物？请只用一个英文单词回答"},
#                         {
#                             "type": "image_url",
#                             "image_url": {
#                                 "url": f"data:image/jpeg;base64,{image_base64}"
#                             }
#                         }
#                     ]
#                 }
#             ]
#         )

#         result = response.choices[0].message.content.lower()
#         print("AI识别结果:", result)

#         menus = Menu.objects.filter(tags__icontains=result)

#         return render(request, "ai_upload.html", {
#             "result": result,
#             "menus": menus
#         })

    return render(request, "ai_upload.html")

def cart_view(request):

    cart = request.session.get("cart", {})

    items = []
    total = 0

    for menu_id, quantity in cart.items():

        menu = Menu.objects.get(id=menu_id)

        subtotal = menu.price * quantity
        total += subtotal

        items.append({
            "menu": menu,
            "menu_id": menu_id,
            "quantity": quantity,
            "subtotal": subtotal
        })

    # ⭐⭐⭐关键：只取可用 coupon
    coupons = Coupon.objects.filter(
        user=request.user,
        is_used=False,
        expires_at__gt=timezone.now()
    )

    return render(request, "cart.html", {
        "items": items,
        "total": total,
        "coupons": coupons
    })

@csrf_exempt
def add_to_cart(request):
    if request.method == "POST":
        data = json.loads(request.body)

        menu_id = str(data.get("id"))
        quantity = int(data.get("quantity", 1))

        cart = request.session.get("cart", {})

        if menu_id in cart:
            cart[menu_id] += quantity
        else:
            cart[menu_id] = quantity

        request.session["cart"] = cart

        return JsonResponse({"status": "success"})

def menu_detail(request, menu_id):
    item = Menu.objects.get(id=menu_id)

    data = {
        "name": item.name,
        "description": item.description,
        "price": str(item.price),
        "image": item.image.url if item.image else ""
    }

    return JsonResponse(data)

def menu_list(request):

    menus = Menu.objects.all()
    recommended_cakes = Menu.objects.none()

    if request.user.is_authenticated:

        # ⭐1. 用户偏好（注册选择）
        pref_flavors = request.user.preferred_flavors.all()

        # ⭐2. 订单行为
        orders = OrderItem.objects.filter(order__user=request.user)

        order_flavors = list(
            orders.values_list('menu__flavors__name', flat=True)
        )

        order_flavors = [f for f in order_flavors if f]

        # ⭐3. 合并推荐源
        flavor_names = list(pref_flavors.values_list("name", flat=True)) + order_flavors

        print("FLAVOR LIST:", flavor_names)

        if flavor_names:

            recommended_cakes = (
                Menu.objects
                .filter(flavors__name__in=flavor_names)
                .distinct()
            )

        print("RECOMMENDED COUNT:", recommended_cakes.count())

    return render(request, "menu.html", {
        "menus": menus,
        "recommended_cakes": recommended_cakes
    })

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("/menu/")
        else:
            return render(request, "login.html", {"error": "ユーザー名またはパスワードが正しくありません"})

    return render(request, "login.html")
