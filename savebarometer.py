#! /usr/bin/python
'''
This saves data gathered for fence top barometer using mqtt to
a database on my house NAS.
'''
import logging
import datetime
import time
import signal
import MySQLdb as mdb
import sys, os
import shlex
import json
import paho.mqtt.client as mqtt

from houseutils import getHouseValues, lprint, dbTime, dbTimeStamp

def handleBarometer(data):
    try:
        jData = json.loads(data)
    except ValueError as err:
        lprint(err)
        lprint("The buffer:")
        lprint(str(msg.payload))
        return
    #print jData
    pressure = jData["Barometer"]["pressure"]
    temperature = jData["Barometer"]["temperature"]
    #print "Pressure is: " + pressure
    #print "Temperature is: " + temperature
    try:
        dbconn = mdb.connect(host=dbHost, user=dbUser, passwd=dbPassword, db=dbName)
        c = dbconn.cursor()
        c.execute("insert into barometer (reading, utime)"
            "values(%s, %s);",
            (pressure,dbTimeStamp()))
        c.execute("insert into ftemperature (reading, utime)"
            "values(%s, %s);",
            (temperature,dbTimeStamp()))
        dbconn.commit()
    except mdb.Error, e:
        lprint ("Database Error %d: %s" % (e.args[0],e.args[1]))
    dbconn.close()
    
def logIt(text):
    mqttc.publish("Desert-Home/Log","{}, {}".format(processName, text));

# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, rc):
    print("Connected with result code "+str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(("Desert-Home/Device/Barometer",0))

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    #print(msg.topic+" "+str(msg.payload))
    if msg.topic == 'Desert-Home/Device/Barometer':
        logIt("got barometer")
        handleBarometer(msg.payload)
    else:
        lprint("got odd topic back: {}".format(msg.topic))
        logIt("got odd topic back: {}".format(msg.topic))

#-----------------------------------------------------------------
# get the stuff from the houserc file
hv = getHouseValues()
# the database where I'm storing weather stuff
#-------------------------------------------------  
# get the values out of the houserc file
hv = getHouseValues()
dbName = hv["weatherDatabase"]
dbHost = hv["weatherHost"]
dbPassword = hv["weatherPassword"]
dbUser = hv["weatherUser"]
#
# Now the mqtt server that will be used
processName = os.path.basename(sys.argv[0])
mqttc = mqtt.Client(client_id=processName)
mqttServer = hv["mqttserver"]
mqttc.connect(mqttServer, 1883, 60)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
try:
    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    lprint ("Going into the mqtt wait loop")
    mqttc.loop_forever()
except KeyboardInterrupt:
    lprint("Cntl-C from user");
              
lprint(processName,"Done")
sys.stdout.flush()
sys.exit("")