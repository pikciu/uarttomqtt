#!/usr/bin/env python3

import ssl
import sys
import re
import json
import os.path
import argparse
from time import time, sleep, localtime, strftime
from configparser import ConfigParser
import paho.mqtt.client as mqtt
import serial

if False:
    # will be caught by python 2.7 to be illegal syntax
    print('Sorry, this script requires a python3 runtime environment.', file=sys.stderr)

# Argparse
parser = argparse.ArgumentParser()
parser.add_argument('--config_dir', help='set directory where config.ini is located', default=sys.path[0])
parse_args = parser.parse_args()


# Eclipse Paho callbacks - http://www.eclipse.org/paho/clients/python/docs/#callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('MQTT connection established', flush=True)
    else:
        print('Connection error with result code {} - {}'.format(str(rc), mqtt.connack_string(rc)))
        #kill main thread
        os._exit(1)


def on_publish(client, userdata, mid):
    pass

def on_message(client, userdata, message):
    value = message.payload.decode('utf-8')
    match = re.search('{}/(\d+)/(\d+)/(\d+)/command'.format(base_topic), message.topic)
    if match:
        device_id_l = match.group(1)
        code_l = match.group(2)
        channel_l = match.group(3)
        command = 'AT+WRTDEVOPTION={},{},{},{}\r\n'.format(device_id_l, code_l, channel_l, value)
        print('Sending command {}'.format(command), flush=True)
        uart.write(command.encode())

# Load configuration file
config_dir = parse_args.config_dir

config = ConfigParser(delimiters=('=', ), inline_comment_prefixes=('#'))
config.optionxform = str
try:
    with open(os.path.join(config_dir, 'config.ini')) as config_file:
        config.read_file(config_file)
except IOError:
    print('No configuration file "config.ini"', flush=True)
    sys.exit(1)

base_topic = config['MQTT'].get('base_topic', '').lower()

# MQTT connection
print('Connecting to MQTT broker ...', flush=True)
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_publish = on_publish
mqtt_client.on_message = on_message

if config['MQTT'].getboolean('tls', False):
    # According to the docs, setting PROTOCOL_SSLv23 "Selects the highest protocol version
    # that both the client and server support. Despite the name, this option can select
    # “TLS” protocols as well as “SSL”" - so this seems like a resonable default
    mqtt_client.tls_set(
        ca_certs=config['MQTT'].get('tls_ca_cert', None),
        keyfile=config['MQTT'].get('tls_keyfile', None),
        certfile=config['MQTT'].get('tls_certfile', None),
        tls_version=ssl.PROTOCOL_SSLv23
    )

mqtt_username = os.environ.get("MQTT_USERNAME", config['MQTT'].get('username'))
mqtt_password = os.environ.get("MQTT_PASSWORD", config['MQTT'].get('password', None))

if mqtt_username:
    mqtt_client.username_pw_set(mqtt_username, mqtt_password)
try:
    mqtt_client.connect(os.environ.get('MQTT_HOSTNAME', config['MQTT'].get('hostname', 'localhost')),
                        port=int(os.environ.get('MQTT_PORT', config['MQTT'].get('port', '1883'))),
                        keepalive=config['MQTT'].getint('keepalive', 60))
except:
    print('MQTT connection error. Please check your settings in the configuration file "config.ini"', flush=True)
    sys.exit(1)
else:
    mqtt_client.loop_start()
    sleep(1.0) # some slack to establish the connection

mqtt_client.subscribe('{}/+/+/+/command'.format(base_topic))

uart = serial.Serial(
    port=config['UART'].get('port'),
    baudrate=config['UART'].getint('baudrate', 115200)
)

while not uart.isOpen():
    pass

device_id=None
code=None
channel=None

print('Ready', flush=True)

while True:
    line = uart.readline().decode('utf-8')
    
    match = re.search('^ID: (\d+)', line)
    if match:
        device_id = match.group(1)
        continue

    match = re.search('^CODE: (\d+)', line)
    if match:
        code = match.group(1)
        continue

    match = re.search('^CHANNEL: (\d+)', line)
    if match:
        channel = match.group(1)
        continue

    match = re.search('^VALUE: (\d+)', line)
    if match:
        value = match.group(1)
        topic = '{}/{}/{}/{}/state'.format(base_topic, device_id, code, channel)
        print('Publish topic: {} value: {}'.format(topic, value), flush=True)
        mqtt_client.publish(topic, value)


