# DomoticzEarthquake
This is a Domoticz Plugin to get (near) Realtime Earthquake Notifications

Gets the information from EMSC-SeismicPortal from http://www.seismicportal.eu/realtime.html with a long-lived websocket connection.

Requirement: You have to set the latitude and longitude of your Domoticz Installation from Settings/Location part.

It has 4 parameters:
1. Radius1: In Kilometers, specify the radius from your Location in which earthquakes larger than "Minimum Magnitude in Radius1" will be notified, e.g. 200
2. Radius2: In Kilometers, specify the radius from your Location in which earthquakes larger than "Minimum Magnitude in Radius2" will be notified. e.g. 500
3. Minimum Magnitude in Radius1: Specify a minimum Richter Scale magnitude for Radius1. e.g. 3.5
4. Minimum Magnitude in Radius2: Specify a minimum Richter Scale magnitude for Radius2. e.g. 6

The numbers in e.g. in the parameters above are suggested values.
