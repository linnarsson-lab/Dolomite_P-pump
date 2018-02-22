#======================================================================================================
# smFISH Dolomite Pump Control
#
# Program to communicate with the Dolomite P-Pump and program a specific protocol
# Python 2
# Platform Linux
# Author: Lars Borm
# Date: 2015
#
# The program consists of 4 main parts: 
# (1) Make a connection with the pump, 
# (2) functions to communicate with the pump,
# (3) functions to cummunicate with the user (both in terminal and via Push)
# (4) protocols to do a sequence of pump commands
#
#======================================================================================================
# User instructions:
#Before using this code you need to manually add the USB adress to this file. And set up a Pushbullet 
#account to receive updates through push messages.
#
#   Set up serial connection
#You can find the adres of the pump by running in a python console:
#"from serial.tools import list_ports"
#"print list(list_ports.comports())"
#plug and unplug the device to see which adres is added to the list.
#The adres should look something like: "/dev/ttyUSBX"
#Then paste the adres in the USER SETUP box below. (line 59)

#On linux you might not have acces to the USB port. Change the acces using "sudo chmod 666 /dev/ttyUSBX"
#
#   Set up pushbullet connection
# Make an account on : https://www.pushbullet.com/
# Gop to settings
# Create your "Access Token"
# Paske the access token together with your name in the "push_users" dictionary (line 63)
# Install the Pushbullet python interface https://github.com/randomchars/pushbullet.py
# 
#
#======================================================================================================
# Import modules

# serial communication over usb
import serial # package to communicate with devices over a serial port
from serial.tools import list_ports # list_port to find the device port path
# pump to computer deciphering
import struct # translate received bytes
# time
import time
from datetime import datetime
#flush
import sys
# Pushbullet
from pushbullet import Pushbullet

#======================================================================================================
# (0) USER SETUP
#======================================================================================================
#Paste the pump USB adres here:
pump_port = None

#Paste username and pushbullet key here:
#push_users = {Name: access token}
push_users = { None: None}

#======================================================================================================
# (1) Make a connection with the pump
#======================================================================================================

# find path to port the pump is connected to. The pump is the last in the all_ports list. Typical addres: /dev/ttyUSBX
if pump_port == None:
    all_ports = list(list_ports.comports())
    pump_port = all_ports[(len(all_ports)-1)]
    pump_port = str(pump_port[0])

#-----------------------------------------------------------------------------------------------------

# If you get error 13: access denied (linux):
# sudo chmod 666 /dev/ttyUSBX
import os
bashCommand = "sudo chmod 666 %s" % pump_port
os.system(bashCommand)

#-----------------------------------------------------------------------------------------------------	
# Connect to pump
ser = serial.Serial(
	port = pump_port,
	baudrate = 115200,
	bytesize=serial.EIGHTBITS,
	stopbits=serial.STOPBITS_ONE,
	parity=serial.PARITY_NONE,
	timeout = 3)


#======================================================================================================
# (2) functions to communicate with the pump
#======================================================================================================

# Construct 12 bit message in the requested format
def message_builder(message_type, location, value):
	global message
	message = []
	message_for_checksum = []
		
	# Template message, 11 bits (the last is a checksum and is appended later)
	byte_list = [2,1,0,0,0,0,0,0,0,0,0]
	byte_list[2] = message_type
	
	# Location	
	if message_type == 1 or message_type == 2: # 1 = write data to memory pump, 2 = read data from certain location in pump memory
		byte_list[4] = location
	elif message_type == 4: # 4 means the streaming of data
		print 'Up to 4 locations can be streamed. Give 0 as input if not all 4 are used.'
		byte_list[3] = raw_input('Location 1: ')
		byte_list[4] = raw_input('Location 2: ')
		byte_list[5] = raw_input('Location 3: ')
		byte_list[6] = raw_input('Location 4: ')
	
	# Value to be written, divided over the 4 message bytes
	byte_list[7] = (value % 256**4) / 256**3
	byte_list[8] = (value % 256**3) / 256**2
	byte_list[9] = (value % 256**2) / 256**1
	byte_list[10] = (value % 256**1) / 256**0

	# Translate to hex
	for item in byte_list:
		message.append (chr(item))
		message_for_checksum.append('{0:#0{1}x}'.format(item,4))
		
	# Calculate checksum, bitwise exclusive OR of the 11 previous bytes
	checksum = 0
	for byte in message_for_checksum:
		checksum ^= int(byte, 16)
	message.append(chr(checksum))
	
	# Join message
	message = ''.join(message)
	 
#-----------------------------------------------------------------------------------------------------	
# Collect message from the pump to the PC
def read_output():
	global response
	time.sleep(0.5)
	
	# A normal message consists of 12 bytes. 
	if ser.inWaiting() != 12 :
		print "\nThere are: " + str(ser.inWaiting()) + "bytes in waiting, not expected. \nThe interpreter will run but probably only one of the messages is relevant."
		b = str(str(ser.inWaiting()) + 'B')
		response = ser.read(ser.inWaiting())
		response = struct.unpack(b, response)
		print  b + " Response: " + str(response)
		
	else:
		response = ser.read(12)
		response = struct.unpack('12B', response)
		
#-----------------------------------------------------------------------------------------------------	
# Translate received bytes into meaning
def message_interpreter(response):
	if len(response) == 12:
		if response[2] == 1:
			response_message = (response[7] * (256**2)) + (response[8] * (256**2)) + (response[9] * 256) + response[10]
			print "	Read request response: " + str(response_message)
			print "	Pump response: " + str(response)
		elif response[2] == 2:
			print '	Pump response: OK'
		elif response[2] == 3:
			if response[3] == 1:
				print '	Checksum error'
			elif response[3] == 2:
				print '	Command unknown'
				print "	Pump response: " + str(response)
			elif response[3] == 3:
				print '	Invalid data, out of range address of value'
				print "	Pump response: " + str(response)
			else:
				print '	Timeout, Communications timeout failure'
				print "	Pump response: " + str(response)
		elif response[2] == 4:
			print '	Firmware version: ' + str(response[3]) + '.'  + str(response[4]) + '.'  + str(response[5]) + '.'  + str(response[6])
		else:
			print "Unidentifiable message type"
	else:
		for n in range(len(response)/12):
			print "Interpreted response " + str(n+1) + ":"
			if response[2] == 1:
				response_message = (response[7] * (256**2)) + (response[8] * (256**2)) + (response[9] * 256) + response[10]
				print "	Read request response: " + str(response_message)
				print "	Pump response: " + str(response)
			elif response[2] == 2:
				print '	Pump response: OK'
			elif response[2] == 3:
				if response[3] == 1:
					print '	Checksum error'
				elif response[3] == 2:
					print '	Command unknown'
					print "	Pump response: " + str(response)
				elif response[3] == 3:
					print '	Invalid data, out of range address of value'
					print "	Pump response: " + str(response)
				else:
					print '	Timeout, Communications timeout failure'
					print "	Pump response: " + str(response)
			elif response[2] == 4:
				print '	Firmware version: ' + str(response[3]) + '.'  + str(response[4]) + '.'  + str(response[5]) + '.'  + str(response[6])
			else:
				print "Unidentifiable message type"
		print "Try to continue with the experiment. If not possible, restart the program and pump.\n"

#-----------------------------------------------------------------------------------------------------	
# PUTTING ABOVE FUNCTIONS TOGETHER
# Construct, send, collect, translate messages and wait until wash step is done
def pump_command(message_type, location, value, duration_minutes):
	message_builder(message_type, location, value) #Make message
	ser.write(message) #Send message to pump
	read_output() #Collect the output
	message_interpreter(response) #Translate the output to human readable
	
	duration_seconds = duration_minutes * 60
	time.sleep(duration_seconds) #Duration of this process

#======================================================================================================
# (3) functions to cummunicate with the user (both in terminal and via Push)
#======================================================================================================

# Instructions for user when buffer has to be changed. 
def buffer_change(volume, buff):
	print "Close valve."
	print "Place at least " + str(volume) + " ml of " + str(buff) + " into the pump. (10% extra)"
	print "Make sure the pump is closed and valves are open."
	raw_input("Press Enter if buffer is changed and valves are open...")
	print

#-----------------------------------------------------------------------------------------------------	
# Calculate end time of wash step
def duration(x):
	now = datetime.now()
	number_of_hours = x / 60
	h = now.hour + number_of_hours
	if h > 24:	#repeat this with 48 if you want to enable a 2 day timer.
		h = h - 24
	m = now.minute + (x -(number_of_hours * 60))
	if m > 60:
		m = m - 60
		h += 1

	return '%s:%s:%s' % (h, m, now.second)

#-----------------------------------------------------------------------------------------------------	
# Prepare and send an Push notification via Pushbullet
# Using https://www.pushbullet.com/ together with the python interface https://github.com/randomchars/pushbullet.py

def sent_push(short_message, long_message, operator):
	
	try:
	    adres = push_users[operator]
	except Exception:
	    print('operator is not in the push users dictionay')
	
	try:
		pb = Pushbullet(adres)
		push = pb.push_note(short_message, long_message)
	except Exception:
		print "Error: unable to send push, check adres key, internet connection or account settings"


#======================================================================================================
# (4) Command pump
#======================================================================================================


def simple_function():
    #Ask for input
    while True:
		operator = raw_input("Enter the operator: ")
		if operator in push_users.keys():
			break
		else:
		    print('Operator: {}, not in push_user dict. Please correct spelling or add operator to dictionary'.format(operator))
		    cont = raw_input('Press C if you want to continue without push messages: ')
		    if cont == 'C':
		        break
	flow_speed = int(raw_input('\nSpecify flow speed in ul/min: '))#the pump wants the flow rate in pico litre / second. 166 ul/min is 1/6th of the maximum speed of 1000 ul/min
	flow_speed = (flow_speed/60) * 1000000
	
    #Tare the pump
    print "Tare the pump. Disconnect the air supply. Open pump chamber. Make sure there is no flow in the system. Duration = 1 minute"
	raw_input("Press Enter when ready for tare...")
	print "Wait until tare is done."
	pump_command(1,78,2,1)
    
    #Set pump into flow control mode
    pump_command(1,77,1,0) #Set pump to flow control mode (in stead of pressure control)
	
    #Set flow rate
    pump_command(1,79,flow_speed,0) #Set flow speed according to the number of used chambers in pl/sec
	print "Connect air supply (max 10 bar)"
	raw_input("Press Enter to continue...")
	
    #Pump twice for 2 minutes with 3 minutes rest
    print "*** Wash 1/2. Done: " + str(duration(10)) + "***"
	pump_command(1,78,1,2) #Pump for 2 min
	pump_command(1,78,0,3) #Return pump to idle for 3 min
    
    print "*** Wash 2/2. ***"
	pump_command(1,78,1,2) #Pump for 2 min
	pump_command(1,78,0,3) #Return pump to idle for 3 min
    
    #Request user buffer change
        #Notify using push
    long_message = 'Please place 2ml of PBS in the pump'
	sent_push('Replace buffer',long_message, operator)
        #Notify on terminal
    buffer_change(2, "PBS") 
        
    #Pump for 5 minutes
    print "*** Wash 1/1. ***"
	pump_command(1,78,1,5) #Pump for 2 min
	pump_command(1,78,0,0) #Return pump to idle
	print('\nSimple function completed')





