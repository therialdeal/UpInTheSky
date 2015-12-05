import requests
import json
import urllib2
import urllib
import geocoder
import getopt
import sys

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
	geoc = geocoder.google(zipcode)
	jgeoc = geoc.json
	latitude = jgeoc['lat']
	longitude = jgeoc['lng']
	return latitude,longitude

"""
get weather api data
"""
def getData(lat,lon):
	APPID = 'f6bdcce20c3c9e79ba4042d45e85641e'
	url = 'http://api.openweathermap.org/data/2.5/forecast?lat=%s&lon=%s&appid=%s' % (lat,lon,APPID)
	#url = 'http://api.openweathermap.org/data/2.5/forecast/daily?lat=%s&lon=%s&cnt=16&mode=json&appid=%s' %(lat, lon, APPID)
	data = json.load(urllib.urlopen(url))
	with open('data.txt', 'w') as outfile:
		json.dump(data, outfile)

"""
determine from the weather api whether the weather is currently cloudy
"""
def isCloudy(time):
	json_data=open('data.txt').read()
	data = json.loads(json_data)
	for l in data['list']:
		if (l['dt_txt'] == time):
			if((l['clouds']['all']) > 25):
				print('too cloudy')
			else:
				print('skies clear')

"""
round the time to a multiple of three so it can 
be matched with the weather api times.
"""
def roundTime(t):
	justdate = t.split()[0]
	justtime = t.split()[1]
	hour = justtime.split(':')[0]
	hour = int(hour)
	hour = hour - (hour%3)
	corrected = justdate + " %s:00:00" %hour
	return corrected

if __name__ == '__main__':
	try:
		opts, args = getopt.getopt(sys.argv[1:],"z:s:")
	except getopt.GetoptError as err:
		print(err)
	z,n = commandParse(opts,args)
	lat,lng = findLatLon(z)
	print lat,lng
	getData(lat,lng)
	t = roundTime("2015-11-15 13:56:06")
	isCloudy(t)










