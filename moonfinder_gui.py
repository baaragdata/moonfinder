# moonfinder_gui.py

import ephem

import math

import queue
import serial
import threading
import signal
import time
from datetime import datetime, timedelta

import PySimpleGUI as sg

port = "COM6"
DEBUG = True
target_name = None

gpsDict = {}
ser = serial.Serial(port, baudrate = 9600, timeout = 0.5)
print("GPS Serial port " + port + " opened")

gpsQueue = queue.Queue()
moveQueue = queue.Queue()

layout = [  [sg.Text("Observatory:"), sg.Text("Latitude (deg)"), sg.Text("Longitude (deg)"), sg.Text("Height (m)")],
            [sg.Text("", size=10), sg.Text("OBS LAT", key='OBS_Lat', size=10), sg.Text("OBS LONG", 
                                        key='OBS_Long', size=10), sg.Text("OBS Alt", key='OBS_Alt', size=10)],
            [sg.Text("Target:"), sg.Text("Altitude (deg)"), sg.Text("Azimuth (deg)"), sg.Text("Phase (%)")],
            [sg.Text("Moon:", size=10), sg.Text("ALT", key='ALT_text', size=10), sg.Text("AZ", 
                                        key='AZ_text', size=10), sg.Text("Moon Phase", key='MoonPhase', size=10)],
            [sg.Text("Rate:"), sg.Text("ALT Rate", key='ALT_rate'), sg.Text("AZ Rate", key='AZ_rate')],
            [sg.Text("DateTime:"), sg.Text("DateTime", key="DateTime_now"),sg.Text("UTC")],
            [sg.Text("Allignment:"), sg.Button("North"), sg.Button("South"), sg.Button("East"), sg.Button("West")],
            [sg.Text("Move:"), sg.Button("^", size=5), sg.Button("v", size=5), sg.Button("<", size=5), sg.Button(">", size=5)],
            [sg.Text("Target:"), sg.Button("Sun"), sg.Button("Moon")],
            [sg.Text("Track:"), sg.Button("Tracking On"), sg.Button("Tracking Off")],
            [sg.Text("Sync:"), sg.Button("Sync Sun"), sg.Button("Sync Moon")]]

# Create the window
window = sg.Window("MoonFinder", layout, finalize=True)

exit_event = threading.Event()  # Create an event to handle exit

def signal_handler(signal=None, frame=None):
    print('You pressed Ctrl+C!')
    exit_event.set()  # Set the event to exit
    ser.close()
    exit()

signal.signal(signal.SIGINT, signal_handler)


############################################## MAIN PROGRAM ####################################################################


from motors import motors

smc = motors()


''' RAW NEMA STRING
    raw: b'$GPGGA,132420.00,5406.22609,N,00054.12943,W,1,05,6.28,59.2,M,47.2,M,,*7A\r\n'
'''

def parseGPS(data):
    ''' Parses the raw NMEA string into a dictionary of date, lat, lon, alt '''
    global date
    #print ("raw:", data) #prints raw data
    data = data.decode("utf-8")
    if "$GPRMC" in data:
        sdata = data.split(",")
        if sdata[6] == 'V':
            print ("no satellite data available")
            return
        date = sdata[9][4:6] + "/" + sdata[9][2:4] + "/" + sdata[9][0:2]#date
    if "$GPGGA" in data:
        sdata = data.split(",")
        #print(sdata)
        if sdata[6] == '0':
            print ("no satellite data available")
            return
        #print ("---Parsing GPRMC---"),
        time = sdata[1][0:2] + ":" + sdata[1][2:4] + ":" + sdata[1][4:6]
        lat = decode(sdata[2]) #latitude
        dirLat = sdata[3]     #latitude direction N/S
        lon = decode(sdata[4]) #longitute
        dirLon = sdata[5]      #longitude direction E/W
        lonSign = "-" if dirLon == "W" else ""
        alt = sdata[9]     #Altitude in meters
        return {'date':f"20{date} {time}", 'lat':f"{lat}", 'lon':f"{lonSign}{lon}", 'alt':f"{alt}"}

def decode(coord):
    '''Convert DDDMM.MMMMM into decimal degrees '''
    x = coord.split(".")
    head = x[0]
    tail = x[1]
    deg = head[0:-2]
    mins = head[-2:]

    decMins = float(mins + '.' + tail) / 60
    decDeg = int(deg)

    return f"{(decDeg + decMins):.4f}"

def getGPS():
    global gpsDict
    while True:
        if exit_event.is_set():
            break
        data = ser.readline()
        gpsDict = parseGPS(data)
                
        if gpsDict: 
            #print('GPS DATA:', gpsDict)
            gpsQueue.empty()
            gpsQueue.put(gpsDict)


def calcPositions():
    '''Calculate the Moon position based on GPS coordinates / data'''
    global moonAz, moonAlt
    while True:
        if exit_event.is_set():
            break
        try:
            moveData = gpsQueue.get(block=True, timeout=2)
        except queue.Empty:
            print("GPS Queue is empty")
        except Exception as e:
            print(e)
        else:
            # get today's date from gpsDict
            if moveData:
                try:
                    obs
                except NameError:
                    obs = ephem.Observer()
                    obs.lat = moveData['lat']
                    obs.long = moveData['lon']
                    obs.elevation = float(moveData['alt'])
                    obs.date = moveData['date']

                    moon = ephem.Moon(obs)
                    moonAz = math.degrees(moon.az)
                    moonAlt = math.degrees(moon.alt)
                    moonPhase = moon.moon_phase * 100
                    
                else:
                    obs.date = moveData['date']
                    moonAz = math.degrees(moon.az)
                    moonAlt = math.degrees(moon.alt)
                    # Add and subtract 15 seconds to the time and recalculate
                    date_plus = obs.date + (ephem.second * 10)
                    date_minus = obs.date - (ephem.second * 10)
                    moon.compute(obs)

                    obs.date = date_plus
                    moon.compute(obs)
                    plus_moonAz = math.degrees(moon.az)
                    plus_moonAlt = math.degrees(moon.alt)
                    obs.date = date_minus
                    moon.compute(obs)
                    minus_moonAz = math.degrees(moon.az)
                    minus_moonAlt = math.degrees(moon.alt)

                    # azimuth rate
                    az_rate = (plus_moonAz - minus_moonAz)/20.0
                    # altitude rate
                    alt_rate = (plus_moonAlt - minus_moonAlt)/20.0                  

                
                    #print(date_minus, date_plus)
                    #print(f" Moon:     {moon.phase:.2f}")
                    window["OBS_Lat"].update(f"{moveData['lat']}{degSymbol}")
                    window["OBS_Long"].update(f"{moveData['lon']}{degSymbol}")
                    window["OBS_Alt"].update(f"{moveData['alt'][:-1]}m")
                    window["ALT_text"].update(f"{moonAlt:.2f}{degSymbol}")
                    window["AZ_text"].update(f"{moonAz:.2f}{degSymbol}")
                    window["MoonPhase"].update(f"{moonPhase:.2f}%")
                    window["AZ_rate"].update(f"{az_rate:.7f}{degSymbol}/s")
                    window["ALT_rate"].update(f"{alt_rate:.7f}{degSymbol}/s")
                    window["DateTime_now"].update(f"{obs.date}")
                    #print(f" Az: {moonAz}{degSymbol} Alt: {moonAlt}{degSymbol}")
                    #print(f" Az Rate: {az_rate}{degSymbol}/s Alt Rate: {alt_rate}{degSymbol}/s")
                    #print(f" El:       {moonEl:.3f}{degSymbol}")
                
                    # if moonEl > -5:  # Almost above horizon 
                    #     mount.goto(0,0,synchronous=False)
                    # else:         # Below horizon --- for testing purposes
                    #     mount.goto(-10,-moonEl,synchronous=False)
                    if target_name == "Moon":
                        smc.goto(moonAlt,moonAz,synchronous=False)

clacPositionsThread = threading.Thread(target=calcPositions)
clacPositionsThread.start()

degSymbol = u'\N{DEGREE SIGN}'


def get_alt_az_rates(target_name, tstamp, pressure=0.0, temperature=0.0, relative_humidity=0.0, obswl=1):
    """Returns alt, az, alt_rate, az_rate, given a target name. Returns None if name not found.

    target_name is a string such as "Mars"

    tstamp is a python datetime or Astropy Time object

    :return: Alt, Az, Alt deg per sec, Az deg per sec
    :rtype: Tuple of four Floats
    """
    
    if not isinstance(tstamp, Time):
        tstamp = Time(tstamp, format='datetime', scale='utc')
    td = TimeDelta(10, format='sec')
    coords = get_named_alt_az(target_name, tstamp, pressure, temperature, relative_humidity, obswl)
    if coords is None:
        return
    # get coordinates 10 seconds in the past
    # and 10 seconds in the future
    # and set the rates as degrees changed / 20
    coords_minus = get_named_alt_az(target_name, tstamp-td, pressure, temperature, relative_humidity, obswl)
    coords_plus = get_named_alt_az(target_name, tstamp+td, pressure, temperature, relative_humidity, obswl)
    # altitude rate
    alt_rate = (coords_plus[0] - coords_minus[0])/20.0
    # azimuth rate
    # handle case where azimuth crosses the 360 - 0 border
    if coords_minus[1]>270 and coords_plus[1]<90:                   # example  cp = 2, cm = 358
        az_rate = (360 + coords_plus[1] - coords_minus[1])/20.0     # rate = (360 + 2 - 358)/20 = 4/20
    elif coords_minus[1]<90 and coords_plus[1]>270:                 # example cp = 358, cm = 2
        az_rate = (coords_plus[1] - 360 - coords_minus[1])/20.0     # rate = (358 - 360 - 2)/20 = -4/20
    else:
        az_rate = (coords_plus[1] - coords_minus[1])/20.0
    return coords[0], coords[1], alt_rate, az_rate

gpsThread = threading.Thread(target=getGPS)
gpsThread.start()

# Create an event loop
while True:
    event, values = window.read()
    print(event, values)
    # End program if user closes window or
    # presses the OK button
    if event == "OK" or event == sg.WIN_CLOSED:
        signal_handler()
        break
    elif event in ["Sun", "Moon"]:
        if event == "Sun":
            target_name = "Sun"
            window["Sun"].update(button_color=('white', 'red'))
            window["Moon"].update(button_color=('black', 'orange'))
        elif event == "Moon":
            target_name = "Moon"
            window["Sun"].update(button_color=('black', 'orange'))
            window["Moon"].update(button_color=('white', 'red'))
            target_name = "Moon"
        elif event == "North":
            smc.set_pos(0,0)
        elif event == "South":
            smc.set_pos(0,180)
        elif event == "East":
            smc.set_pos(0,90)
        elif event == "West":
            smc.set_pos(0,270)


window.close()
