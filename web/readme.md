todo
----
- read/write db from tuyamqtt


Changelog
---------
- set db path
- basic setup
- user friendly admin panels
    - device show related dps items
    - option selects   
- pre populate db for dpstypes

Install
----
```
python3 manage.py migrate
python3 manage.py createsuperuser
python3 manage.py loaddata dpstype
```

run it
-------
```
python3 manage.py runserver
```

db model
----------
```
settings

devices -< dps - dpstype
```

settings
-------
```
name:str
value:str
```

device
------
```
name:str
topic:str
protocol:str
deviceid:str
localkey:str
ip:str
hass_discovery:bool
```

dps
-----
```
device: int FK
key:int
value:str
via:str (tuya|mqtt)
dpstype:int FK
```

dpstype
----------
```
name:str
valuetype:str (bool, int, str)
range_min:float
range_max:float
discoverytype:str (switch|button|?)
```