# Ecodan controller
# Copyright (C) 2023-2024  Roel Huybrechts

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import datetime

import httpx

from dto.generic import TimePeriodStatsDto, TimeRangeDto, TimestampDto
from dto.solar import SolarProductionDto


class MmeSoleilClient:
    def __init__(self, app, base_url, username, password):
        self.app = app
        self.base_url = base_url

        self.client = httpx.AsyncClient()
        self.client.auth = (username, password)

    async def shutdown(self):
        await self.client.aclose()

    async def get_peak_production(self, start, end, min_kwh, peak_duration_h, order):
        r = await self.client.get(f'{self.base_url}/production/peak', params={
            'start': start,
            'end': end,
            'min_kwh': min_kwh,
            'peak_duration_h': peak_duration_h,
            'order': order,
            'precision': 1,
            'min_temp': 6
        })
        return TimestampDto.from_isoformat(r.json()['result'])

    async def get_production_bounds(self, date=None, min_kw=0):
        if date is None:
            date = datetime.date.today()

        r = await self.client.get(f'{self.base_url}/production/bounds', params={
            'date': date,
            'min_kW': min_kw
        })
        return TimeRangeDto.from_json(r.json())

    async def get_temperature_stats(self, start, end):
        r = await self.client.get(f'{self.base_url}/temperature/stats', params={
            'start': start,
            'end': end
        })
        return TimePeriodStatsDto.from_json(r.json())

    async def get_production_weather(self, start, end):
        r = await self.client.get(f'{self.base_url}/production/weather', params={
            'start': start,
            'end': end
        })
        return SolarProductionDto.from_json(r.json())
