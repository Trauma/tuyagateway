from django.contrib import admin

from .models import Setting, Device, Dps, Dpstype

admin.site.register(Setting)
admin.site.register(Device)
admin.site.register(Dps)
admin.site.register(Dpstype)