#! /usr/bin/python
'''
 This process waits for an HTTP request from someone wanting the
 weather. It reads the data from a MySQL database on my NAS and formats it
 into either JSON for a process interface or a very simple HTML page for
 debugging or just checking around from time to time.
'''
import json
from datetime import datetime, timedelta
from houseutils import lprint, getHouseValues, timer, checkTimer, midnight
from datetime import datetime, timedelta
import sys
import MySQLdb as mdb
import argparse
import cherrypy

def collectWeather():
    global Weather

    dbconn = mdb.connect(host=dbHost, user=dbUser, passwd=dbPassword, db=dbName)
    c = dbconn.cursor()
    c.execute("select reading from ftemperature where utime = "
            "(select max(utime) from ftemperature);")
    Weather["currentOutsideTemp"] = c.fetchone()[0]
    
    c.execute("select reading from rtemperature where utime = "
            "(select max(utime) from rtemperature);")
    Weather["roofTemperature"] = c.fetchone()[0]
    
    c.execute("select speed from wind where utime = "
            "(select max(utime) from wind);")
    Weather["windSpeed"] = c.fetchone()[0]
    
    c.execute("select directionc from wind where utime = "
            "(select max(utime) from wind);")
    Weather["windDirectionC"] = c.fetchone()[0]
    
    c.execute("select directiond from wind where utime = "
            "(select max(utime) from wind);")
    Weather["windDirectionD"] = c.fetchone()[0]
            
    c.execute \
        ("select reading from humidity where utime = "
            "(select max(utime) from wind);")
    Weather["humidity"] = c.fetchone()[0]
    
    c.execute("select reading from barometer where utime = "
            "(select max(utime) from barometer);")
    Weather["currentBarometric"] = c.fetchone()[0]
    
    # Get the cumulative readings
    c.execute("select barometer from daily where utime = %s;",
        (midnight(1),))
    Weather["midnightBarometric"] = c.fetchone()[0]
    
    # now get the rest of the daily items
    c.execute("select windhigh from daily where utime = %s;", \
        (midnight(),))
    Weather["maxWindSpeedToday"] = c.fetchone()[0]
    
    c.execute("select hightemp from daily where utime = %s;",\
        (midnight(),))
    Weather["maxTempToday"] = c.fetchone()[0]
    
    c.execute("select lowtemp from daily where utime = %s;",\
        (midnight(),))
    Weather["minTempToday"] = c.fetchone()[0]
    
    c.execute("select raincount from daily where utime = %s;",\
        (midnight(1),))
    startCount = c.fetchone()[0]
    
    c.execute("select reading  from raincounter where utime = "
            "(select max(utime) from raincounter);")
    endCount = c.fetchone()[0]
    
    Weather["rainToday"] = str((float(endCount) - float(startCount)) * 0.01)
    dbconn.close()

def showData():
    global Weather
    
    returnString = ""
    # fill in the Weather dictionary
    collectWeather()
    # now compose the screen
    returnString += "Temperature on fence: " + str(Weather["currentOutsideTemp"]) + \
        "<br />"
    returnString += "Temperature on roof: " + str(Weather["roofTemperature"]) + \
        "<br />"
    returnString += "Wind Speed: " + str(Weather["windSpeed"]) + "<br />"
    returnString += "Wind Direction: " + Weather["windDirectionC"] + \
        " (" + Weather["windDirectionD"] + ")" + "<br />"
    returnString += "Humidity: " + str(Weather["humidity"]) + "%" + "<br />"
    returnString += "Barometer: " + str(Weather["currentBarometric"]) + \
        " mbar" + "<br />"
    returnString += "<br />"
    returnString += "Midnight Barometer Reading: " + str(Weather["midnightBarometric"]) + \
        " mbar" + "<br />"
    returnString += "High Temperature Today: " + str(Weather["maxTempToday"]) + \
        "<br />"
    returnString += "Low Temperature Today: " + str(Weather["minTempToday"]) + \
        "<br />"
    returnString += "Highest Wind Speed Today: " + str(Weather["maxWindSpeedToday"]) + \
        "<br />"
    returnString += "Rainfall Today: " + Weather["rainToday"] + \
        " inch" + "<br />"
    
    return(returnString)

def keepAlive():
    # this is only to log that the process is still alive
    lprint(" keep alive")

# This is the process interface, it consists of a status report for humans
# and a json output for other things.
class WeatherSC(object):
    @cherrypy.expose
    @cherrypy.tools.json_out() # This allows a dictionary input to go out as JSON
    def status(self):
        collectWeather()
        return Weather
        
    @cherrypy.expose
    def index(self):
        status = "<strong>Desert Home Weather</strong><br /><br />"
        status += showData()
        return status
        
####################### Actually Starts Here ################################    
debug = False
Weather ={ 
    "currentBarometric": "default",
    "midnightBarometric":"default",
    "rainToday": "default",
    "currentOutsideTemp": "default",
    "roofTemperature": "default",
    "humidity": "default",
    "windSpeed" : "default",
    "windDirectionC" : "default",
    "windDirectionD" : "default",
    "maxWindSpeedToday" : "default",
    "maxTempToday" : "default",
    "minTempToday" : "default"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug",
        action = "store_true",
        help='debug flag')
    args = parser.parse_args()
    if args.debug:
        print "Running with debug on"
        debug = True
  
    # the database where I'm storing stuff
    hv = getHouseValues()
    dbName = hv["weatherDatabase"]
    dbHost = hv["weatherHost"]
    dbPassword = hv["weatherPassword"]
    dbUser = hv["weatherUser"]
   # Get the ip address and port number you want to use
    # from the houserc file
    ipAddress=getHouseValues()["giveweather"]["ipAddress"]
    port = getHouseValues()["giveweather"]["port"]
    # periodically put a message into the log to indicate that
    # this is still alive
    keepAliveTimer = timer(keepAlive, minutes=4)
  
    cherrypy.config.update({'server.socket_host' : ipAddress.encode('ascii','ignore'),
                            'server.socket_port': port,
                            'engine.autoreload.on': False,
                            })
    # Subscribe to the 'main' channel in cherrypy with my timer
    cherrypy.engine.subscribe("main", checkTimer.tick)
    lprint ("Hanging on the wait for HTTP message")
    # Now just hang on the HTTP server looking for something to 
    # come in.  The cherrypy dispatcher will update the things that
    # are subscribed which will update the timers so the light
    # status gets recorded.
    cherrypy.quickstart(WeatherSC())
    
    sys.exit("Told to shut down");
    
        
        