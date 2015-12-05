# Assignment 3, Network Applications
# Zawad Chowdhury, Ria Sarkar, Kyle Imhof
# sudo date -s "Sun Nov 29 11:06:10 UTC 2015"
# sudo python icu.py -z 24060 -s 25544

import ephem
import requests
import urllib2
import json
import datetime
import math 
import urllib
import geocoder
import getopt
import sys
import time
import RPi.GPIO as GPIO
import os
import requests.packages.urllib3
requests.packages.urllib3.disable_warnings()

from bs4 import BeautifulSoup
from calendar import timegm
from twilio.rest import TwilioRestClient

global lon, lat, weather, results, satellite, alertedViewing, city, state
alertedViewing = [False]*5

"""
Initalize LEDS
"""
def initLEDs():
    # Setup GPIO as output
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(11, GPIO.OUT) #Pi cobbler pin 17
    GPIO.setup(12, GPIO.OUT) #Pi cobbler pin 18
    GPIO.setup(13, GPIO.OUT) #Pi cobbler pin 27
    GPIO.setup(15, GPIO.OUT) #Pi cobbler pin 22

"""
retrieves the latest TLE based on the input NORAD_CAT_ID.
this information is retrieved from space-track.org
"""
def getTLEs(norad_id):
    print "Retrieving TLE Data..."
    global satellite
    query = "/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/"
    order = "/orderby/ORDINAL%20asc/limit/10/metadata/false"
    s = requests.Session()
    url = "https://www.space-track.org"
    auth_path = "/auth/login"
    creds = {"identity":"zawad@vt.edu","password":"asdfghjkl123456"}
    s.post(url+auth_path,data=creds)
    queryURL = url + query + str(norad_id) + order
    res = requests.get(queryURL,cookies = s.cookies)
    data = res.text
    with open('space-track_data.txt', 'w') as outfile:
        outfile.write(data)
    json_data = json.loads(data)
    satellite = str(json_data[0]["OBJECT_NAME"])
    tle = [0 for i in range(3)]
    tle[0] = str(json_data[0]["TLE_LINE0"])
    tle[1] = str(json_data[0]["TLE_LINE1"])
    tle[2] = str(json_data[0]["TLE_LINE2"])
    printTLEs(n, tle)
    return tle
"""
kelvin to fahrenheit
"""
def toFahrenheit(k):
    return (k-273.15)*1.8000+32.00

"""
prints the 16 day forcast for the area
"""
def printForecast(data):
    global city, state
    print "16 Day Forcast for",city+",",state+":"
    d = [""]*16
    t = [""]*16
    s = [""]*16
    count = 0
    count2 = 0
    count3 = 0
    for l in data.forecast.findAll('time'):
        d[count] = l.get('day')
        count += 1
    for l in data.forecast:
        for temp in l.findAll('temperature'):
            t[count2] = temp.get('day')
            count2 += 1
        for sym in l.findAll('symbol'):
            s[count3] = sym.get('name')
            count3 += 1
    zipped = zip(d,t,s)
    print """   Date     Temp (F)   Forcast"""
    print """================================="""
    
    for z in zipped:
        print  "%s | %4.2f | %s" % \
        (z[0] ,toFahrenheit(float(z[1])),z[2])
    
"""
datetime_from_time converts 
Code taken from StackExchange User harry1795671
Code found here http://space.stackexchange.com/questions/4339/calculating-which-satellite-passes-are-visible
"""
def datetime_from_time(tr):
    year, month, day, hour, minute, second = tr.tuple()
    dt = datetime.datetime(year, month, day, hour, minute, int(second))
    return dt

"""
getVisiblePasses retrieves the next 5 visible passes based on the zip location
- satellite must be above observer's horizon
- sun must below the observer's horizon enough to darken the sky
- satellite must be illuminated by the sun
Code inspired from StackExchange User harry1795671
Code found here http://space.stackexchange.com/questions/4339/calculating-which-satellite-passes-are-visible
"""
def getVisiblePasses(lon, lat, tle):
    global results
    # set up the satellite
    sat = ephem.readtle(str(tle[0]), str(tle[1]), str(tle[2]))
    
    # set up the observer to be in the area code specified the input
    observer = ephem.Observer()
    observer.lat = str(lat)
    observer.long = str(lon)
    observer.pressure = 0
    observer.horizon = 0

    # retreiving the date and time now
    now = datetime.datetime.utcnow()

    #initalizing the sun
    sun = ephem.Sun()
    
    foundFive = 0
    results = []
    time_results = []

    #get weather data
    wData = getData(lat,lon)

    #get the next 5 visible passes
    while foundFive < 5:
        # make sure that we don't go past 15 days beacuse we only have 
        # weather forcast for 15 days
        if datetime_from_time(observer.date) >= now + datetime.timedelta(days=15):
            break
        tr, azr, tt, altt, ts, azs = observer.next_pass(sat)
        #Rise time, Rise azimuth, Maximum altitude time, Maximum altitude, Set time, Set azimuth

        #set the observer date to the time the satellitte is as it's highest point
        observer.date = tt
        
        #compute the sun and sat values respective to the observer
        sun.compute(observer)
        sat.compute(observer)

        #get the angle of the sun 
        sun_alt = math.degrees(sun.alt)

        #make sure it is dark out side, sunlight reflected off of the satellite, and it is clear
        if sat.eclipsed is False and -25 < sun_alt < -10 and isCloudy(tt.datetime().strftime("%Y-%m-%d"),wData):# #and -20 < sun_alt < -4:# and sat.alt > 0:
            foundFive += 1
            time_results.append(datetime_from_time(tt))
            sunr = observer.previous_rising(sun).datetime().strftime("%H:%M:%S") if observer.previous_rising(sun).datetime().strftime("%Y-%m-%d") == tr.datetime().strftime("%Y-%m-%d") else observer.next_rising(sun).datetime().strftime("%H:%M:%S") 
            suns = observer.next_setting(sun).datetime().strftime("%H:%M:%S")  if observer.next_setting(sun).datetime().strftime("%Y-%m-%d") == tr.datetime().strftime("%Y-%m-%d") else observer.previous_setting(sun).datetime().strftime("%H:%M:%S") 

            duration = int((ts - tr) *60*60*24)
            results.append("%s | %4.1f %s | %4.1f %+6.1f  | %5.1f | %d sec | %s | %s | %s" % \
            (tt, math.degrees(sat.alt), direction_name(math.degrees(sat.az)), 
             math.degrees(sat.sublat), math.degrees(sat.sublong), sat.elevation/1000,
             duration, sunr, suns, weather))
            #end if 

        observer.date = ts + 5* ephem.minute
        #end while loop

    printResults()
    return time_results

"""
prints the results 
printing style was inspired by Mark VandeWettering
Can be found here http://brainwagon.org/2009/09/27/how-to-use-python-to-predict-satellite-locations/
"""
def printResults():
    global results, satellite
    print
    print "Next" , len(results), "possible sightings of the" , satellite+":"
    print """    Transet (UTC)     Alt/Azim     Lat/Long     Elev   Duration   Sunrise    Sunset    Weather"""
    print """================================================================================================"""
    for r in results:
        print r
    if len(results) != 5:
        print "Due to weather conditions", satellite ,"will only be viewable", len(results), "times in the next 15 days"
    print
    print "Waiting for Optimus Prime (aka "+satellite+")"

"""
normalize_angle normailzes angle 
Code taken from Maximilian Hoegner <hp.maxi@hoegners.de>
Can be found http://hoegners.de/Maxi/geo/geo.py
"""
def normalize_angle(angle):
    """ Takes angle in degrees and returns angle from 0 to 360 degrees """
    cycles = angle/360.
    normalized_cycles = cycles - math.floor(cycles)
    return normalized_cycles*360.

"""
takes cardinal direction and returns direction in N,E,S,W etc.
Code taken from Maximilian Hoegner <hp.maxi@hoegners.de>
Can be found http://hoegners.de/Maxi/geo/geo.py
"""
def direction_name(angle):
    direction_names = ["N  ","NNE","NE ","ENE","E  ","ESE","SE ","SSE","S  ","SSW","SW ","WSW","W  ","WNW","NW ","NNW"]
    directions_num = len(direction_names)
    directions_step = 360./directions_num
    """ Returns a name for a direction given in degrees. Example: direction_name(0.0) returns "N", direction_name(90.0) returns "O", direction_name(152.0) returns "SSO". """
    index = int(round( normalize_angle(angle)/directions_step ))
    index %= directions_num
    return direction_names[index]

"""
parse command line arguments
"""
def commandParse(opts,args):
    zipcode = ""
    noradid = ""
    if not opts:
        help()
    for switch,command in opts:
        if (switch == "-z"):
            zipcode = command
        if (switch == "-h"):
            help()
        if (switch == "-s"):
            noradid = command
    return zipcode,noradid

"""
help method prints how to use the commandline arguments
"""
def help():
    print "options:"
    print "sudo python icu.py -z [zipcode] -s [noradid]"
    exit(2)

"""
find latitude and longitude from zipcode
"""
def findLatLon(zipcode):
    global city, state
    geoc = geocoder.google(zipcode)
    city = geoc.city
    state = geoc.state
    jgeoc = geoc.json
    latitude = jgeoc['lat']
    longitude = jgeoc['lng']
    return latitude,longitude

"""
get weather data from the openweather api
"""
def getData(lat,lon):
    print "\nRetrieving Weather Data..."
    APPID = 'f6bdcce20c3c9e79ba4042d45e85641e'
    #url = 'http://api.openweathermap.org/data/2.5/forecast?lat=%s&lon=%s&appid=%s' % (lat,lon,APPID)
    url = 'http://api.openweathermap.org/data/2.5/forecast/daily?lat=%s&lon=%s&cnt=16&mode=xml&appid=%s' %(lat, lon, APPID)
    data = urllib.urlopen(url)
    d = BeautifulSoup(data, "html.parser")#, "lxml")
    printForecast(d)
    with open('open-weather_data.txt', 'w') as outfile:
        outfile.write(d.prettify())
    return d

"""
determine from the openweather api whether the weather is currently cloudy
"""
def isCloudy(t, xmlData):
    global lat, lon, weather
    for l in xmlData.forecast.findAll("time"):
        if(l.get('day')==t):
            for cloud in l.find_all('clouds'):
                per = cloud.get('all')
                if(int(per) > 25):
                    return False
                elif(int(per) < 12):
                    weather = "Clear"
                    return True
                else:
                    weather = "Mostly Clear"
                    return True
    weather = " N/A"
    return True

"""
method set up to get TLEs out of a saved data file
inorder to save API queries 
"""
def fakeTLEs(n):
    print "Retrieving TLE Data..."
    print "TLE Data:"
    global satellite
    data = open('space-track_data.txt').read()
    json_data = json.loads(data)
    tle = [0 for i in range(3)]
    satellite = str(json_data[0]["OBJECT_NAME"])
    tle[0] = str(json_data[0]["TLE_LINE0"])
    tle[1] = str(json_data[0]["TLE_LINE1"])
    tle[2] = str(json_data[0]["TLE_LINE2"])
    printTLEs(n, tle)
    return tle

"""
print TLEs
"""
def printTLEs(n, t):
    for i in t:
        print i

"""
infinite loop of waiting to alert user about the satellite
this function will alert the user by:
flashing the LEDS
playing a transformersSound
and texting them as well
"""
def waitForNextPass(timeResults):
    global alertedViewing
    count = 0
    for time in timeResults:
        if time < datetime.datetime.now():
            count += 1
            continue
        elif (time-datetime.datetime.now() < datetime.timedelta(0,0,0,0,15)):
            if alertedViewing[count] == False:
                doAlerts()
                alertedViewing[count] = True
        count += 1 
          
"""
uses the twilio api to send a text message to the user
"""
def sendSMS(text): 
    account_sid = "ACa39a35c46c9214787d910b45de6c95c7"
    auth_token = "fe5970ea3ecb11547221eb6ff064858a"
    client = TwilioRestClient(account_sid, auth_token)
     
    message = client.messages.create(to="+17038695388", from_="+16193618073",
                                     body=text)

"""
alerts the user via led, sound and text message
"""
def doAlerts():
    #print "alerts now"
    global results
    messages = createMessage()
    sendSMS(messages)
    print
    print messages
    GPIO.output(11, GPIO.HIGH)
    time.sleep(.2)
    GPIO.output(11, GPIO.LOW)
    time.sleep(.2)
    GPIO.output(11, GPIO.HIGH)
    time.sleep(.2)
    GPIO.output(11, GPIO.LOW)
    os.system('omxplayer transformersSound.mp3 > /dev/null 2>&1')    
    #os.system('play -n synth .1 sin 261.63 > /dev/null 2>&1')
    #time.sleep(.075)
    #os.system('play -n synth .1 sin 261.63 > /dev/null 2>&1')
    #time.sleep(.075) 
    #os.system('play -n synth .2 sin 261.63 > /dev/null 2>&1')

"""
formats the message for the text based on results
"""
def createMessage():
    global results, satellite
    messages = "\n"
    # print
    messages += "Go check out " + satellite + " it is going to pass over your place in 15 minutes!\n"
    nextPass = results.pop(0).split('|')
    dirLength = len(nextPass[1].split(' '))
    if(dirLength == 4):
        direction = nextPass[1].split(' ')[2]
        deg = nextPass[1].split(' ')[1]
    else:
        direction = nextPass[1].split(' ')[3]
        deg = nextPass[1].split(' ')[2]
    messages += "Just go outside, look to your " + direction + " and look up about " + deg + " degrees."
    return messages


if __name__ == '__main__':
    try:
        opts, args = getopt.getopt(sys.argv[1:],"z:s:")
    except getopt.GetoptError as err:
        print(err)
    global lat, lon
    z,n = commandParse(opts,args)
    initLEDs()
    lat,lon = findLatLon(z)
    tle = getTLEs(n)
    # tle = fakeTLEs(n)
    time_results = getVisiblePasses(lon, lat, tle)
    try:
        while(1):
            waitForNextPass(time_results)
    except KeyboardInterrupt:
        pass
    finally:
	print
        print "Goodbye..."
        GPIO.cleanup()
        
    
