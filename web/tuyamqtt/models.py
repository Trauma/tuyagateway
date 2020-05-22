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
    protocol = models.CharField(max_length=16)
    deviceid = models.CharField(max_length=64)
    localkey = models.CharField(max_length=64)
    ip = models.CharField(max_length=32)
    hass_discovery = models.BooleanField()
    def __str__(self):
        return self.name

class Dpstype(models.Model):
    name = models.CharField(max_length=64)
    valuetype = models.CharField(max_length=16)
    range_min = models.IntegerField(default=0)
    range_max = models.IntegerField(default=255)
    discoverytype = models.CharField(max_length=16)
    def __str__(self):
        return self.name

class Dps(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    key = models.IntegerField()
    value = models.CharField(max_length=16)
    via = models.CharField(max_length=8)
    dpstype = models.ForeignKey(Dpstype, on_delete=models.CASCADE)
    def __str__(self):
        return self.device.name+" dps:"+str(self.key)




