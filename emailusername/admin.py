from django.contrib import admin

from .models import User

class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_active', 'is_admin', 'password']

admin.site.register(User, UserAdmin)
