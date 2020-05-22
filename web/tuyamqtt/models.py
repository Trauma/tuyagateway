from django.db import models

# Create your models here.
class Setting(models.Model):

    name = models.CharField(max_length=64)
    value = models.CharField(max_length=256)
    def __str__(self):
        return self.name

class Device(models.Model):

    name = models.CharField(max_length=32)
    topic = models.CharField(max_length=200)

    protocol_choices = [
        ('3.1', '3.1'),
        ('3.3', '3.3'),
    ]

    protocol = models.CharField(max_length=16, choices=protocol_choices, default= '3.3')
    deviceid = models.CharField(max_length=64)
    localkey = models.CharField(max_length=64)
    ip = models.GenericIPAddressField()
    hass_discovery = models.BooleanField()
    def __str__(self):
        return self.name

class Dpstype(models.Model):

    name = models.CharField(max_length=64)

    valuetype_choices = [
        ('bool','Boolean'),
        ('int','Integer'),
        ('str','String')
    ]
    valuetype = models.CharField(max_length=16, choices=valuetype_choices, default='bool')
    range_min = models.IntegerField(default=0)
    range_max = models.IntegerField(default=255)

    discoverytype_choices = [
        ('light','Light'),
        ('switch','Switch'),
        ('sensor','Sensor'),
        ('binary_sensor','Binary Sensor'),
    ]
    discoverytype = models.CharField(
        max_length=16, 
        choices=discoverytype_choices, 
        default='light'
    )
    def __str__(self):
        return self.name

class Dps(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    key = models.IntegerField()
    value = models.CharField(max_length=16)

    via_choices = [
        ('tuya', 'Tuya'),
        ('mqtt', 'MQTT'),
    ]

    via = models.CharField(max_length=8, choices=via_choices, default='tuya')
    dpstype = models.ForeignKey(Dpstype, on_delete=models.CASCADE)
    def __str__(self):
        return self.device.name+":"+str(self.key)




