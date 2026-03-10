from django.contrib import admin
from .models import Product

class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_name', 'price', 'stock', 'category', 'modified_date', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('product_name', 'description')
    prepopulated_fields = {'slug': ('product_name',)}

admin.site.register(Product, ProductAdmin)