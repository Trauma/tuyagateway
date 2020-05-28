FROM python:3.6

WORKDIR /usr/src/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install tuyamqtt

COPY . .
# use main for now
CMD [ "python", "./main.py" ]