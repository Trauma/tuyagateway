db model
----------

settings

devices -< dps - dpstype


settings
-------
id:int PK
name:str
value:str


device
------
id:int PK
name:str
topic:str
protocol:str
device_id:str
device_key:str
ip:str
hass_discovery:bool

dps
-----
id:int PK
deviceid: int FK
dps_nr:int
value:str
via:str (tuya|mqtt)
dpstypeid:int FK

dpstype
----------
id:int PK
name:str
valuetype:str (bool, int, str)
range_min:float
range_max:float
discoverytype:str (switch|button|?)