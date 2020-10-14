#!/usr/bin/env python3

import ssl
import sys
import re
import json
import os.path
import argparse
from time import time, sleep, localtime, strftime
from collections import OrderedDict
from colorama import init as colorama_init
from colorama import Fore, Back, Style
from configparser import ConfigParser
from unidecode import unidecode
import paho.mqtt.client as mqtt
import sdnotify
import serial
from signal import signal, SIGPIPE, SIG_DFL
signal(SIGPIPE,SIG_DFL)

if False:
    # will be caught by python 2.7 to be illegal syntax
    print('Sorry, this script requires a python3 runtime environment.', file=sys.stderr)

# Argparse
parser = argparse.ArgumentParser()
parser.add_argument('--config_dir', help='set directory where config.ini is located', default=sys.path[0])
parse_args = parser.parse_args()

# Intro
colorama_init()

# Systemd Service Notifications - https://github.com/bb4242/sdnotify
sd_notifier = sdnotify.SystemdNotifier()

# Logging function
def print_line(text, error = False, warning=False, sd_notify=False, console=True):
    timestamp = strftime('%Y-%m-%d %H:%M:%S', localtime())
    if console:
        if error:
            print(Fore.RED + Style.BRIGHT + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL, file=sys.stderr)
        elif warning:
            print(Fore.YELLOW + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL)
        else:
            print(Fore.GREEN + '[{}] '.format(timestamp) + Style.RESET_ALL + '{}'.format(text) + Style.RESET_ALL)
    timestamp_sd = strftime('%b %d %H:%M:%S', localtime())
    if sd_notify:
        sd_notifier.notify('STATUS={} - {}.'.format(timestamp_sd, unidecode(text)))


# Eclipse Paho callbacks - http://www.eclipse.org/paho/clients/python/docs/#callbacks
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print_line('MQTT connection established', console=True, sd_notify=True)
        print()
    else:
        print_line('Connection error with result code {} - {}'.format(str(rc), mqtt.connack_string(rc)), error=True)
        #kill main thread
        os._exit(1)


def on_publish(client, userdata, mid):
    #print_line('Data successfully published.')
    pass

def on_message(client, userdata, message):
	value = message.payload.decode('utf-8')
	match = re.search('{}/(\d+)/(\d+)/command'.format(base_topic), message.topic)
	if match:
		device_id_l = match.group(1)
		code_l = match.group(2)
		command = 'AT+WRTDEVOPTION={},{},0,{}\r\n'.format(device_id_l, code_l, value)
		print_line('Sending command {}'.format(command), error=False, sd_notify=True)
		uart.write(command.encode())

# Load configuration file
config_dir = parse_args.config_dir

config = ConfigParser(delimiters=('=', ), inline_comment_prefixes=('#'))
config.optionxform = str
try:
    with open(os.path.join(config_dir, 'config.ini')) as config_file:
        config.read_file(config_file)
except IOError:
    print_line('No configuration file "config.ini"', error=True, sd_notify=True)
    sys.exit(1)

base_topic = config['MQTT'].get('base_topic', '').lower()

print_line('Configuration accepted', console=False, sd_notify=True)

# MQTT connection
print_line('Connecting to MQTT broker ...')
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
    print_line('MQTT connection error. Please check your settings in the configuration file "config.ini"', error=True, sd_notify=True)
    sys.exit(1)
else:
	mqtt_client.loop_start()
	sleep(1.0) # some slack to establish the connection

mqtt_client.subscribe('{}/+/+/command'.format(base_topic))

uart = serial.Serial(
	port=config['UART'].get('port'),
	baudrate=config['UART'].getint('baudrate', 115200)
)

while not uart.isOpen():
	pass

sd_notifier.notify('READY=1')

device_id=None
code=None

while True:
	line = uart.readline().decode('utf-8')
    print_line(line)
	match = re.search('^ID: (\d+)', line)
	if match:
		device_id = match.group(1)
		continue

	match = re.search('^CODE: (\d+)', line)
	if match:
		code = match.group(1)
		continue

	match = re.search('^VALUE: (\d+)', line)
	if match:
		value = match.group(1)
		topic = '{}/{}/{}/state'.format(base_topic, device_id, code)
		print_line('Publish topic: {} value: {}'.format(topic, value), sd_notify=True)
		mqtt_client.publish(topic, value)


