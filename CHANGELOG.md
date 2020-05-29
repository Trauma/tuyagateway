Changelog
==================
_v1.1.0_
- make readme enduser friendly #44
- check config values #35
- branch protection rules #42
- Ctrl+C does not stop server #3
- Remove availability logic from TuyaMQTTEntity.status #26
- add commandline arg for testing tuyaface #43
- workflow publish to pypi #39
- Autodiscovery #28
- add setup.py #38
- black, flake, mypi, pre-commit #41
- Ctrl+C does not stop server #3
- listen for kill signal from mqttdevices
- device config via topic is rather crude
  - https://github.com/TradeFace/mqttdevices has to solve this
  - add tuyamqtt Autodiscovery #28
- Remove availability logic from TuyaMQTTEntity.status #26

_v1.0.0_
- clean up
- bump tuyaface to v1.2.0
- removed hass_discovery
- moved UI basics -> https://github.com/TradeFace/mqttdevices 
- bump tuyaface to v1.1.7 
  - near instant status updates on manual device handling
- bump tuyaface to v1.1.6
- implemented logger and removed custom debugger
- tuyaface to v1.1.5
- clean up dockerfile
- check requirements.txt 
- replaced entities.json with sqlite db
- only publish onchange
- added via mqtt/tuya
- thread per device
- pytuya replaced by https://github.com/TradeFace/tuya