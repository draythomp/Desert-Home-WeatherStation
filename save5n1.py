#!/usr/bin/python
# watch out for cr in line above
'''
This process waits for input from standard in and updates a MySQL database
on my NAS. It relies on a modified rtl_433 specifically adapted to the 
AcuRite 5n1 sensor. So, rtl_433 gets the data, transmits it, the pi picks it
up using software defined radio the data gets passed to this process and 
recorded in a database. This process has no interaction with a person.
'''
import sys
import json
import time
from apscheduler.schedulers.background import BackgroundScheduler
import urllib2
import BaseHTTPServer
import logging
import MySQLdb as mdb
from datetime import datetime, timedelta
from houseutils import getHouseValues, lprint, dbTimeStamp, midnight
from time import localtime, strftime

def recordInDatabase():
    #lprint("Recording weather data")
    # First update the daily totals in the Weather dictionary
    getDailys()
    if ("default" in Weather.values()):
        lprint("Weather data not ready yet")
        lprint(Weather)
        return
    dbconn = mdb.connect(host=dbHost, user=dbUser, passwd=dbPassword, db=dbName)
    c = dbconn.cursor()
    try: 
        c.execute("insert into rtemperature (reading, utime)"
            "values(%s, %s);",
            (Weather["roofTemperature"],dbTimeStamp()))
        c.execute("insert into humidity (reading, utime)"
            "values(%s, %s);",
            (Weather["humidity"],dbTimeStamp()))
        c.execute("insert into wind (speed, directionc, directiond, utime)"
            "values(%s,%s,%s,%s);",
            (Weather["windSpeed"],
            Weather["windDirectionC"],
            Weather["windDirectionD"],
            dbTimeStamp()))
        c.execute("insert into raincounter (reading, utime)"
            "values(%s, %s);",
            (Weather["rainCounter"],dbTimeStamp()))
        dbconn.commit() # just in case the code below fails
        # now adjust the daily mins and maxs
        # This record gets updated all day and a new one gets created
        # whenever a reading comes in after midnight. This means that
        # the cumulative number are held under midnight of the previous
        # day. This makes it a little confusing when calculating things
        # like rainfall because you get the record for yesterday to 
        # represent the last reading of yesterday. As in max(today) - 
        # yesterday will give you today's rainfall.
        c.execute('''INSERT INTO daily
            (hightemp, lowtemp, windhigh, barometer, raincount, utime)
            VALUES
                (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                hightemp = values(hightemp),
                lowtemp = values(lowtemp),
                windhigh = values(windhigh),
                barometer = values(barometer),
                raincount = values(raincount); ''',
            (Weather["maxTempToday"], 
            Weather["minTempToday"], 
            Weather["maxWindSpeedToday"], 
            Weather["latestBarometric"],
            Weather["rainCounter"],
            midnight(),))
        dbconn.commit()
    except mdb.Error, e:
        lprint ("Database Error %d: %s" % (e.args[0],e.args[1]))
    dbconn.close()
    #lprint("Finished recording items");

def getDailys():
    # get maxs, mins and such out of the database to pick
    # up where we left off in case of failure and restart.
    # Midnight yesterday is considered the first instant of today.
    m = midnight(1)  # This time was recorded as the last reading yesterday
    n = dbTimeStamp()
    dbconn = mdb.connect(host=dbHost, user=dbUser, passwd=dbPassword, db=dbName)
    c = dbconn.cursor()
    c.execute \
        ("select min(reading/1.0) from ftemperature where utime between %s and %s;",
        (m, n))
    Weather["minTempToday"] = c.fetchone()[0]

    c.execute \
        ("select max(reading/1.0) from ftemperature where utime between %s and %s;",
        (m, n))
    Weather["maxTempToday"] = c.fetchone()[0]

    c.execute \
        ("select max(speed/1.0) from wind where utime between %s and %s;",
        (m, n))
    Weather["maxWindSpeedToday"] = c.fetchone()[0]
    
    c.execute \
        ("SELECT reading FROM barometer ORDER BY utime DESC LIMIT 1;")
    Weather["latestBarometric"] = c.fetchone()[0]
    dbconn.close()
    
def midnightReset():
    Weather["maxWindSpeedToday"] = Weather["windSpeed"]
    Weather["maxTempToday"] = Weather["currentOutsideTemp"]
    Weather["minTempToday"] = Weather["currentOutsideTemp"]
    
def recordInLog():
    lprint(sys.argv[0]," Running")
    lprint(Weather)


direction={"NNW":337.5,"NW":315,"WNW":292.5,"W":270,
        "WSW":247.5,"SW":225,"SSW":202.5,"S":180,
        "SSE":157.5,"SE":135,"ESE":112.5,"E":90,
        "ENE":67.5,"NE":45,"NNE":22.5,"N":0}

Weather ={ 
    #"currentBarometric": "default", The barometer is not read here
    "latestBarometric":"default",
    "rainCounter": "default",
    #"currentOutsideTemp": "default", This is from the fence sensor also
    "roofTemperature": "default",
    "humidity": "default",
    "windSpeed" : "default",
    "windDirectionC" : "default",
    "windDirectionD" : "default",
    "maxWindSpeedToday" : "default",
    "maxTempToday" : "default",
    "minTempToday" : "default"
    }
#-------------------------------------------------  
# get the values out of the houserc file
hv = getHouseValues()
dbName = hv["weatherDatabase"]
dbHost = hv["weatherHost"]
dbPassword = hv["weatherPassword"]
dbUser = hv["weatherUser"]

buff = ''
data = ""
char = ""
#-------------------------------------------------
logging.basicConfig()
#------------------If you want to schedule something to happen -----
scheditem = BackgroundScheduler()
# This resets the daily items at midnight; actually, just a few
# seconds before midnight to avoid problems with overshoot
scheditem.add_job(midnightReset, 'cron', hour=23, minute=59, second=50)

# the "I'm alive right now" message
scheditem.add_job(recordInLog, 'interval', minutes=30)
# Update the database periodically
scheditem.add_job(recordInDatabase, 'interval', seconds=60)
scheditem.start()

recordInLog()
#get daily cumulative numbers
getDailys()
print "initial readings", Weather;
'''
 Now just hang up in a loop reading the radio output.
 The data is held and updated in the Weather dictionary with database
 updates to record it on minute intervals handled by the timer above.
'''
while True:
    try:
        char = sys.stdin.read(1) #This is a blocking read,
        # (you have no idea how hard it was to discover this)
        # an end of file on a piped in input is a length of 
        # zero.  There's about a thousand wrong answers out there
        # and I never did find the right one.  Thank goodness
        # for good old trial and error.
        if len(char) == 0:
            break # the pipe is gone, just exit the process
        else:
            buff += char;
        if buff.endswith('\n'):
            try:
                data = json.loads(buff[:-1])
            except ValueError as err:
                lprint(err)
                lprint("The buffer:")
                lprint(buff)
                buff = ''
                continue
            # First I'm going to check the incoming to be sure
            # the radio didn't decode the wrong sensor head, or
            # a different device didn't slip something past the
            # decoder
            if data["sensorId"]["SID"] != '92':
                lprint("Error, Wrong sensor ID = ", data["sensorId"]["SID"])
                buff =''
                continue
            if data["channel"]["CH"] != 'A':
                lprint("Error, Wrong Channel = ", data["channel"]["CH"])
                buff =''
                continue
            if data["battLevel"]["BAT"] != '7':
                 lprint("Error, Check Battery = ", data["battLevel"]["BAT"])
           
            # Now, fill in the Weather dictionary for use by
            # everything else
            # beginning with the five readings from the sensor head
            Weather["windSpeed"] = data["windSpeed"]["WS"]
            Weather["windDirectionC"] = data["windDirection"]["WD"]
            Weather["roofTemperature"] = data["temperature"]["T"]
            Weather["humidity"] = data["humidity"]["H"]
            Weather["rainCounter"] = data["rainCounter"]["RC"]
            if (Weather["windDirectionC"] in direction):
                Weather["windDirectionD"] = direction[Weather["windDirectionC"]]
            # Now update max wind speed (temps are taken from another sensor)
            if (Weather["maxWindSpeedToday"] == "default"):
                Weather["maxWindSpeedToday"] = data["windSpeed"]["WS"]
            if (Weather["maxWindSpeedToday"] is None):
                Weather["maxWindSpeedToday"] = data["windSpeed"]["WS"]
                
            if(float(Weather["maxWindSpeedToday"]) < float(data["windSpeed"]["WS"])):
                Weather["maxWindSpeedToday"] = data["windSpeed"]["WS"]
            # and start the buffer over from scratch
            buff = ''

    except KeyboardInterrupt:
        lprint("Cntl-C from user");
        break;
              
scheditem.shutdown(wait=False)
lprint(sys.argv[0],"Done")
sys.stdout.flush()
sys.exit("")