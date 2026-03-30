from .models import Cart, CartItem
from .views import _cart_id

def counter(request):
    cart_count = 0
    if 'admin' in request.path:
        return {}
    else:
        try:
            if request.user.is_authenticated:
                # 1. Look for items assigned to the LOGGED-IN USER
                cart_items = CartItem.objects.all().filter(user=request.user)
            else:
                # 2. Look for items assigned to the GUEST SESSION
                cart = Cart.objects.filter(cart_id=_cart_id(request))
                cart_items = CartItem.objects.all().filter(cart=cart[:1])
            
            # Sum up the quantities
            for cart_item in cart_items:
                cart_count += cart_item.quantity
        except Cart.DoesNotExist:
            cart_count = 0
            
    return dict(cart_count=cart_count)