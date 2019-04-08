#!/usr/bin/env python3

from aiohttp import web

from joule import ReaderModule
from joule.utilities import time_now
import asyncio
import numpy as np


class WeatherStationReader(ReaderModule):
    """ Read Ambient Weather Station """

    async def setup(self, parsed_args, app, output):
        self.output = output
        app = web.Application()
        app["pipe"] = self.output
        app.add_routes([web.get('/endpoint',ambient_weather)])
        self.ambient_runner = web.AppRunner(app)
        await self.ambient_runner.setup()
        site = web.TCPSite(self.ambient_runner,'localhost',8000)
        await site.start()
        
    async def run(self, parsed_args, output):
        while not self.stop_requested:
            await asyncio.sleep(1)
        await self.ambient_runner.cleanup()

        
async def ambient_weather(request):
    pipe = request.app["pipe"]
    keys = ["tempf","humidity","hourlyrainin",
            "baromrelin","windspeedmph","windgustmph",
            "winddir","solarradiation","uv"]

    data = [time_now()]
    for key in keys:
        data.append(float(request.query[key]))
    await pipe.write(np.array([data]))
    return web.Response(text="OK")
            
def main():
    r = WeatherStationReader()
    r.start()
    
if __name__ == "__main__":
    main()
