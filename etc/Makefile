init:
	pip3 install -r requirements.txt

install:
	sudo sed  's|{path}|'${PWD}'|' ./config/tuyamqtt.service > /etc/systemd/system/tuyamqtt.service
	sudo cp ./config/tuyamqtt.conf /etc/tuyamqtt.conf
	sudo systemctl enable tuyamqtt.service
	sudo systemctl start tuyamqtt.service

docker:	
	docker build -t tuyamqtt .