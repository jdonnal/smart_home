#!/usr/local/bin/python3

from joule import ReaderModule
from joule.utilities import time_now
import asyncio
import requests
import numpy as np
import time


class WeatherData(ReaderModule):
    " Retrieve data from openweathermap"

    def custom_args(self, parser):
        grp = parser.add_argument_group("module",
                                        "module specific arguments")
        grp.add_argument("--api_key",
                         required=True,
                         help="Open Weather API key")
        grp.add_argument("--city_id",
                         required=True,
                         help="Open Weather City ID")
                        
    async def run(self, parsed_args, output):
        while(1):
            req = requests.get("http://api.openweathermap.org/data/2.5/" +
                               "weather?" +
                               "id=%s&units=imperial&"%parsed_args.city_id +
                               "APPID=%s"%parsed_args.api_key)
            resp = req.json()

            temp = resp['main']['temp']
            pressure = resp['main']['pressure']*0.02953 #convert to inHg
            humidity = resp['main']['humidity']
            windspeed = resp['wind']['speed']
            winddir = resp['wind']['deg']
            
            ts = time_now()
            await output.write(np.array([[ts, temp, humidity,
                                              pressure, windspeed,
                                              winddir]]))
            await asyncio.sleep(60)  # every minute

            
if __name__ == "__main__":
    r = WeatherData()
    r.start()



