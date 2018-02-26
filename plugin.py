"""
<plugin key="SeismicPortal" name="Eartquake EMSC Data" author="febalci" version="1.0.0">
    <params>
        <param field="Mode2" label="Radius1 (km)" width="150px" required="true" default="40000"/>
        <param field="Mode3" label="Radius2 (km)" width="150px" required="true" default="50000"/>
        <param field="Mode4" label="Min Magnitude in Radius1" width="150px" required="true" default="2"/>
        <param field="Mode5" label="Min Magnitude in Radius2" width="150px" required="true" default="3"/>
        <param field="Mode6" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""

import Domoticz
import json
from math import radians, cos, sin, asin, sqrt
import struct
import calendar
from datetime import datetime, timedelta

class BasePlugin:
    wsConn = None
    wsping = bytes([0x89, 0x80, 0x5b, 0x63, 0x68, 0x84])
    myHomelat = myHomelon = 0
    nextConnect = 2
    oustandingPings = 0
    wsHeader = "GET /standing_order/websocket HTTP/1.1\r\n" \
                "Host: www.seismicportal.eu\r\n" \
                "User-Agent: Domoticz/1.0\r\n" \
                "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n" \
                "Accept-Language: en-US,en;q=0.5\r\n" \
                "Accept-Encoding: gzip, deflate\r\n" \
                "Sec-WebSocket-Version: 13\r\n" \
                "Origin: http://www.seismicportal.eu\r\n" \
                "Sec-WebSocket-Key: qqMLBxyyjz9Tog1bll7K6A==\r\n" \
                "DNT: 1\r\n" \
                "Connection: keep-alive, Upgrade\r\n" \
                "Pragma: no-cache\r\n" \
                "Cache-Control: no-cache\r\n" \
                "Upgrade: websocket\r\n\r\n"

    def __init__(self):
        #self.var = 123
        return

    def onStart(self):
        global minRadius, maxRadius, minMagnitude, maxMagnitude
        Domoticz.Log("onstart Called")

        if (Parameters["Mode6"] == "Debug"):
            Domoticz.Debugging(1)
        
        # Get the location from the Settings
        if not "Location" in Settings:
            Domoticz.Log("Location not set in Preferences")
            return False
        
        # The location is stored in a string in the Settings
        loc = Settings["Location"].split(";")
        self.myHomelat = float(loc[0])
        self.myHomelon = float(loc[1])
        Domoticz.Debug("Coordinates from Domoticz: " + str(self.myHomelat) + ";" + str(self.myHomelon))

        if self.myHomelat == None or self.myHomelon == None:
            Domoticz.Log("Unable to parse coordinates")
            return False
 
        minRadius = float (Parameters["Mode2"])
        maxRadius = float (Parameters["Mode3"])
        minMagnitude = float(Parameters["Mode4"])
        maxMagnitude = float(Parameters["Mode5"])

        if (len(Devices) == 0):
            Domoticz.Device(Name='Earthquake', Unit=1, TypeName="Alert", Used=1).Create()
            Domoticz.Debug("Device created.")

        self.wsConn = Domoticz.Connection(Name="EmscConn", Transport="TCP/IP", Protocol="None", Address="www.seismicportal.eu", Port="80")
        self.wsConn.Connect()

        DumpConfigToLog()
        Domoticz.Heartbeat(40)

    def onStop(self):
        Domoticz.Log("onStop called")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called")
        if (Status == 0):
            self.isConnected = True
            Connection.Send(self.wsHeader) #Upgrade Connection to WebSocket
            Domoticz.Debug("Connected successfully to the server")
        else:
            self.isConnected = False
            Domoticz.Debug("Failed to connect ("+str(Status)+") to server with error: "+Description)
        return

    def onMessage(self, Connection, Data, Status, Extra):
        Domoticz.Log("onMessage called")

        HEADER, = struct.unpack("!H", Data[:2])
        wsData = Data[2:]
        FIN    = (HEADER >> 15) & 0x01
        RSV1   = (HEADER >> 14) & 0x01
        RSV2   = (HEADER >> 13) & 0x01
        RSV3   = (HEADER >> 12) & 0x01
        OPCODE = (HEADER >>  8) & 0x0F
        MASKED = (HEADER >>  7) & 0x01
        LEN    = (HEADER >>  0) & 0x7F

        if LEN == 126:
            LEN, = struct.unpack("!H", wsData[:2])
            wsData = wsData[2:]
        elif LEN == 127:
            LEN, = struct.unpack("!4H", wsData[:8])
            wsData = wsData[8:]

        if Data[:2]==b'\x81\x7e': #Earthquake Message
            eqjson = wsData.decode('utf8')
            eqdata = json.loads(eqjson)
            Domoticz.Debug(str(eqdata))
            action = eqdata["action"]
            mag = eqdata["data"]["properties"]["mag"]
            lat = eqdata["data"]["properties"]["lat"]
            lon = eqdata["data"]["properties"]["lon"]
            time = eqdata["data"]["properties"]["time"]
            time = isoutc_to_local(time)

            location = eqdata["data"]["properties"]["flynn_region"]
            distance = haversine(lat,lon,self.myHomelat,self.myHomelon)
            Domoticz.Debug ("Magnitude = "+str(mag))
            Domoticz.Debug ("Distance = "+str(int(distance))+" km")
            eqshow = False
            # If the earthquake is within the given parameters: 
            if action == "create": # New Earthquake - "update" is updating values of an earlier earthquake
                Domoticz.Debug(location)
                if distance < minRadius:
                    if float(mag) > minMagnitude:
                        eqshow = True
                elif distance < maxRadius:
                    if float(mag) > maxMagnitude:
                        eqshow = True
                elif float(mag) > 8:
                    eqshow = True

                # Alertbox Color:
                if mag < 3:
                    magnitude=0
                elif mag < 4:
                    magnitude=1
                elif mag < 5:
                    magnitude=2
                elif mag < 6:
                    magnitude=3
                else:
                    magnitude=4
                
                if eqshow:
                    Domoticz.Log(str(mag)+' - '+location)
                    UpdateDevice(1,magnitude,str(mag)+' - '+str(int(distance))+' km - '+location+' - '+str(time))#0=gray, 1=green, 2=yellow, 3=orange, 4=red
                
        elif Data[:2]==b'\x8a\x00':#PONG message from the server
            self.oustandingPings = self.oustandingPings - 1
            Domoticz.Debug('Pong received')

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")
        self.isConnected = False 
        
    def onHeartbeat(self):
        if (self.wsConn.Connected() == True):
            if (self.oustandingPings > 3):
                Domoticz.Debug("Ping Timeout, Disconnect")
                self.wsConn.Disconnect()
                self.nextConnect = 0
            else:
                self.wsConn.Send(self.wsping) #PING message to Server
                Domoticz.Debug("Ping sent")
                self.oustandingPings = self.oustandingPings + 1
        else:
            # if not connected try and reconnected every 2 heartbeats
            self.oustandingPings = 0
            self.nextConnect = self.nextConnect - 1
            if (self.nextConnect <= 0):
                self.nextConnect = 2
                self.wsConn.Connect()
        return

global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Connection, Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions

def UpdateDevice(Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (Unit in Devices):
        if (Devices[Unit].nValue != nValue) or (Devices[Unit].sValue != sValue):
            Devices[Unit].Update(nValue, str(sValue))
            Domoticz.Log("Update "+str(nValue)+":'"+str(sValue)+"' ("+Devices[Unit].Name+")")
    return

def haversine(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # haversine formula 
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 

    # 6367 km is the radius of the Earth
    km = 6367 * c
    return km 

def isoutc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    ztime = datetime.strptime(utc_dt, '%Y-%m-%dT%H:%M:%S.%fZ')
    timestamp = calendar.timegm(ztime.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert ztime.resolution >= timedelta(microseconds=1)
    return local_dt.replace(microsecond=ztime.microsecond)

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
