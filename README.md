<p align="center"><img width="50%" alt="TuyaMQTT logo" src="https://github.com/TradeFace/tuyamqtt/blob/development/docs/tuyamqtt_logo.png?raw=true"></p>

Listens on MQTT topic and routes requests to Tuya devices, based on a one to one topic translation in e.g. Home-Assistant config-files. 1:1 topic translation is limited to simple tasks (like switching ON/OFF); only boolean values. 

TuyaMQTT uses [TuyaFace](https://github.com/TradeFace/tuya) to communicate locally (no cloud connection needed) with your tuya devices.

In v1.1 Tuya device configuration can be done with [GismoCaster](https://github.com/TradeFace/gismocaster). In which you can set discovery messages for both TuyaMQTT and Home Assistant and opens up the ability to set boolean/integer/float/string types. 

The goal for version v1.2 is to add input/output processing functions and to improve on HA message values.  


<p align="center"><img alt="Network" src="https://github.com/TradeFace/tuyamqtt/blob/development/docs/network_bg.png?raw=true"></p>



[Docs](https://github.com/TradeFace/tuyamqtt/wiki)
================
https://github.com/TradeFace/tuyamqtt/wiki

Get involved!
================
Anyone who is willing to test, write code, add documentation, etc. is welcome to make a [contribution](https://github.com/TradeFace/tuyamqtt/CONTRIBUTING.md). 




Acknowledgements
=================
- https://github.com/emontnemery development tuyaclient and implementation in tuyamqtt
- https://github.com/jkerdreux-imt testing tuyaclient
- https://github.com/SDNick484 testing protocol 3.1 reimplementation
