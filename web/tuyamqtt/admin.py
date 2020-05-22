from django.contrib import admin

from .models import Setting, Device, Dps, Dpstype



class DpsInline(admin.StackedInline):
    model = Dps

class DeviceAdmin(admin.ModelAdmin):
     inlines = [DpsInline,]
     
admin.site.register(Setting)
admin.site.register(Device, DeviceAdmin)
# admin.site.register(Dps)
admin.site.register(Dpstype)