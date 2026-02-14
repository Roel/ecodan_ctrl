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

import httpx

from dto.heatpump import HeatPumpSetpointDto, HeatPumpStatusDto
from dto.generic import TimeDataDto, TimePeriodStatsDto


class HabClient:
    def __init__(self, app, base_url, username, password):
        self.app = app
        self.base_url = base_url

        self.client = httpx.AsyncClient(timeout=30)
        self.client.auth = (username, password)

    async def shutdown(self):
        await self.client.aclose()

    async def get_current_state(self):
        r = await self.client.get(f'{self.base_url}/heatpump/status')
        return HeatPumpStatusDto(**r.json())

    async def get_setpoint(self):
        r = await self.client.get(f'{self.base_url}/heatpump/setpoint')
        return HeatPumpSetpointDto(**r.json())

    async def get_last_legionella_start(self):
        r = await self.client.get(f'{self.base_url}/legionella/last')
        result = TimeDataDto.from_json(r.json())
        self.app.log.debug(
            f'Hab reports last legionella cycle started on {result.timestamp}')
        return result

    async def get_current_dhw_temp(self):
        r = await self.client.get(f'{self.base_url}/dhw/temp')
        return TimeDataDto.from_json(r.json())

    async def get_current_outside_temp(self):
        r = await self.client.get(f"{self.base_url}/outside/temp")
        return TimeDataDto.from_json(r.json())

    async def get_baseline_consumption(self):
        r = await self.client.get(f'{self.base_url}/consumption/baseline')
        return TimePeriodStatsDto.from_json(r.json())

    async def get_current_consumption(self):
        r = await self.client.get(f'{self.base_url}/consumption/current')
        return TimeDataDto.from_json(r.json())

    async def get_current_net_power(self):
        r = await self.client.get(f'{self.base_url}/power/net/current')
        return TimeDataDto.from_json(r.json())

    async def get_daily_production(self):
        r = await self.client.get(f'{self.base_url}/production/daily')
        return TimeDataDto.from_json(r.json())

    async def get_house_temperature(self, start=None, end=None):
        params = {}
        if start is not None:
            params['start'] = start
        if end is not None:
            params['end'] = end

        r = await self.client.get(f'{self.base_url}/house/temp', params=params)

        if r.status_code == httpx.codes.OK:
            return TimePeriodStatsDto.from_json(r.json())

    async def get_simulated_price_baseline(self, start, end):
        data = {
            "data": [
                {"timestamp": start.isoformat(), "net_power": 750},
                {"timestamp": end.isoformat(), "net_power": 750},
            ]
        }

        r = await self.client.post(f"{self.base_url}/price/simulate/total", json=data)

        if r.status_code == httpx.codes.OK:
            return TimePeriodStatsDto.from_json(r.json())

    async def get_simulated_price_detail(self, start, end):
        data = {
            "data": [
                {"timestamp": start.isoformat(), "net_power": 750},
                {"timestamp": end.isoformat(), "net_power": 750},
            ]
        }

        r = await self.client.post(
            f"{self.base_url}/price/simulate/total/detail", json=data
        )

        if r.status_code == httpx.codes.OK:
            return [TimeDataDto.from_json(i) for i in r.json()]
