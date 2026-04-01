import razorpay
import json
import datetime
from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from carts.models import CartItem
from .models import Order, Payment, OrderProduct
from .forms import OrderForm
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.http import HttpResponse , JsonResponse


# Initialize Razorpay Client
client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

def place_order(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    if cart_items.count() <= 0:
        return redirect('store')

    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
    tax = (2 * total) / 100
    grand_total = total + tax

    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            # Store billing info
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()

            # Generate order number
            order_number = datetime.date.today().strftime("%Y%m%d") + str(data.id)
            data.order_number = order_number
            data.save()

            # Razorpay Order Creation
            # razorpay_order = client.order.create({
            #     "amount": int(grand_total * 100),
            #     "currency": "INR",
            #     "payment_capture": 1
            # })

            context = {
                'order': data,
                'cart_items': cart_items,
                'total': total,
                'tax': tax,
                'grand_total': grand_total,
                # 'razorpay_order_id': razorpay_order['id'],
                'razorpay_merchant_key': settings.RAZORPAY_KEY_ID,
            }
            return render(request, 'orders/payments.html', context)
    return redirect('checkout')

def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])

    # 1. Store payment details
    payment = Payment(
        user = request.user,
        payment_id = body['razorpay_payment_id'],
        payment_method = 'Razorpay',
        amount_paid = order.order_total,
        status = 'Completed',
    )
    payment.save()

    # 2. Update Order
    order.payment = payment
    order.is_ordered = True
    order.save()

    # 3. Move Cart items to OrderProduct
    cart_items = CartItem.objects.filter(user=request.user)
    for item in cart_items:
        orderproduct = OrderProduct()
        orderproduct.order_id = order.id
        orderproduct.payment = payment
        orderproduct.user_id = request.user.id
        orderproduct.product_id = item.product_id
        orderproduct.quantity = item.quantity
        orderproduct.product_price = item.product.price
        orderproduct.ordered = True
        orderproduct.save()
        
        # Save Variations
        cart_item = CartItem.objects.get(id=item.id)
        product_variation = cart_item.variations.all()
        orderproduct = OrderProduct.objects.get(id=orderproduct.id)
        orderproduct.variations.set(product_variation)
        orderproduct.save()

        # 4. Reduce the quantity of the sold products (Inventory Management)
        product = item.product
        product.stock -= item.quantity
        product.save()

    # 5. Clear Cart
        CartItem.objects.filter(user=request.user).delete()

        # 6 . send order received email
        mail_subject = 'Thank you for your order!'

        message = render_to_string('orders/order_received_email.html', {
            'user': request.user,
            'order':order,

        })

        to_email = request.user.email
        send_email = EmailMessage(mail_subject, message, to=[to_email])
        send_email.send()

    # 5. Clear Cart
    CartItem.objects.filter(user=request.user).delete()

    return JsonResponse({'order_number': order.order_number, 'payment_id': payment.payment_id})

def order_complete(request):
    order_number = request.GET.get('order_number') # Fixed to uppercase GET
    payment_id = request.GET.get('payment_id')    # Fixed to uppercase GET

    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)
        payment = Payment.objects.get(payment_id=payment_id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity

        context = {
            'order': order,
            'ordered_products': ordered_products,
            'payment': payment,
            'transID': payment.payment_id,
            'subtotal': subtotal,
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')