init:
	pip3 install -r requirements.txt

install:
	sudo sed  's|{path}|'${PWD}'|' ./etc/tuyagateway.service > /etc/systemd/system/tuyagateway.service
	sudo cp ./etc/tuyagateway.conf /etc/tuyagateway.conf
	sudo systemctl enable tuyagateway.service
	sudo systemctl start tuyagateway.service

docker:	
	docker build -t tuyagateway .