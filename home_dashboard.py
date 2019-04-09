#!/usr/local/bin/python3

import aiohttp
from datetime import datetime
import asyncio
import os
import time
import aiohttp_jinja2
import jinja2

from joule import FilterModule
from joule.utilities import time_now
from joule.models.pipes import EmptyPipe

CSS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'css')
JS_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'js')
WEBFONT_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'webfonts')

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), 'assets', 'templates')


class HomeDashboard(FilterModule):
    """ Retrieve data from openweathermap """

    def custom_args(self, parser):
        grp = parser.add_argument_group("module",
                                        "module specific arguments")
        grp.add_argument("--api_key",
                         required=True,
                         help="Open Weather API key")
        grp.add_argument("--city_id",
                         required=True,
                         help="Open Weather City ID")
        grp.add_argument("--weather_stream",
                         required=True,
                         help="Weather Station Data")
        grp.add_argument("--power_stream",
                         required=True,
                         help="Electrical Power Data")

    async def setup(self, parsed_args, app, inputs, outputs):
        self.city_id = parsed_args.city_id
        self.api_key = parsed_args.api_key
        self.weather_stream = await self.node.stream_get(parsed_args.weather_stream)
        self.power_stream = await self.node.stream_get(parsed_args.power_stream)

        loader = jinja2.FileSystemLoader(TEMPLATES_DIR)
        aiohttp_jinja2.setup(app, loader=loader)

    async def run(self, parsed_args, inputs, outputs):
        while True:
            await asyncio.sleep(1)

    def routes(self):
        return [aiohttp.web.get('/', self.index),
                aiohttp.web.static('/assets/css', CSS_DIR),
                aiohttp.web.static('/assets/js', JS_DIR),
                aiohttp.web.static('/assets/webfonts', WEBFONT_DIR)
                ]

    @aiohttp_jinja2.template('index.jinja2')
    async def index(self, request):
        forecast = await self._get_forecast()
        weather = await self._get_current_weather()
        display_elements = ["Temperature", "Humidity", "Hourly Rain", "UV", "Wind Speed"]
        power_data = await self._get_power_data()
        power_str = str(power_data).replace("None", "null")
        return {"forecast": forecast, "weather_stream": self.weather_stream,
                "weather": weather, "display_elements": display_elements,
                "power_data": power_str}

    async def _get_forecast(self):
        url = ("http://api.openweathermap.org/data/2.5/" +
               "forecast?" +
               "id=%s&units=imperial&" % self.city_id +
               "APPID=%s" % self.api_key)

        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                print(resp.status)
                data = await resp.json()
                num_forecasts = data['cnt']
                # one forecast per 24 hours
                forecasts = []
                for i in range(7, num_forecasts, 8):
                    forecasts.append(Forecast(data['list'][i]))
                return forecasts

    async def _get_current_weather(self):
        pipe = await self.node.data_read(self.weather_stream, start=time_now() - 60 * 60 * 1e6)
        try:
            data = await pipe.read()
        except EmptyPipe:
            return []
        pipe.consume(len(data))
        await pipe.close()
        return data['data'][-1]

    async def _get_power_data(self):
        one_day = 24 * 60 * 60 * 1e6
        one_week = 7 * one_day
        time_window = one_day
        pipe = await self.node.data_read(self.power_stream, start=time_now() - time_window, max_rows=1000)
        power_data = []
        offset = _utc_offset().total_seconds()*1e3

        while True:
            try:
                data = await pipe.read(flatten=True)
            except EmptyPipe:
                break
            pipe.consume(len(data))
            power_data += [[(d[0] / 1e3) + offset, (d[1] + d[8]) / 1e3] for d in data]
            if pipe.end_of_interval:
                power_data.append(None)
        await pipe.close()

        return power_data


class Forecast:
    def __init__(self, data):
        self.datetime = _ts_to_local(data['dt'])
        self.temp_min = data['main']['temp_min']
        self.temp_max = data['main']['temp_max']
        self.temp = data['main']['temp']
        self._weather_icon = data['weather'][0]['icon']
        self.description = data['weather'][0]['description']

    @property
    def weather_icon(self):
        if self._weather_icon.startswith("01"):  # clear sky
            return "fa-sun"
        elif self._weather_icon.startswith("02"):  # few clouds
            return "fa-cloud-sun"
        elif self._weather_icon.startswith("03"):  # scattered clouds
            return "fa-cloud"
        elif self._weather_icon.startswith("04"):  # broken clouds
            return "fa-cloud"
        elif self._weather_icon.startswith("09"):  # shower rain
            return "fa-cloud-sun-rain"
        elif self._weather_icon.startswith("10"):  # rain
            return "fa-cloud-showers-heavy"
        elif self._weather_icon.startswith("11"):  # thunderstorm
            return "fa-bolt"
        elif self._weather_icon.startswith("13"):  # snow
            return "fa-snowflake"
        elif self._weather_icon.startswith("50"):  # mist
            return "fa-smog"
        else:
            return "fa-question-circle"


def _ts_to_local(ts):
    utc_datetime = datetime.utcfromtimestamp(ts)
    return utc_datetime + _utc_offset()

def _utc_offset():
    now_timestamp = time.time()
    return datetime.fromtimestamp(now_timestamp) - datetime.utcfromtimestamp(now_timestamp)

def main():
    r = HomeDashboard()
    r.start()


if __name__ == "__main__":
    main()
