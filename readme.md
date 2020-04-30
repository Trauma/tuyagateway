TuyaMQTT
==================

Listens on MQTT topic and routes requests to Tuya devices, based on a one to one topic translation. 

Docs
================
https://github.com/TradeFace/tuyamqtt/wiki


Todo
===================
- check config values
- device config via topic is rather crude
  - simple interface?
- implement https://www.home-assistant.io/docs/mqtt/discovery/
- implement logger and remove custom debugger

- check requirements.txt 
- clean exit issue #3

Changelog
==================
- tuyaface to v1.1.0
- replaced entities.json with sqlite db
- only publish onchange
- added via mqtt/tuya
- thread per device
- pytuya replaced by https://github.com/TradeFace/tuya

Acknowledgements
=================
- https://github.com/SDNick484 for testing protocol 3.1 reimplementation



