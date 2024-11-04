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


class EcodanClient:
    def __init__(self, app, base_url, username, password):
        self.app = app
        self.base_url = base_url

        self.client = httpx.AsyncClient()
        self.client.auth = (username, password)

    async def shutdown(self):
        await self.client.aclose()

    async def set_dhw_target_temp(self, target_temp):
        self.app.log.debug(
            f'Calling ecodan to set DHW target tank temperature to: {target_temp}')
        r = await self.client.put(f'{self.base_url}/tank/target_temp', json={
            'value': target_temp
        })
        return r.raise_for_status()

    async def set_heating_target_temp(self, target_temp):
        self.app.log.debug(
            f'Calling ecodan to set heating target temperature to: {target_temp}')
        r = await self.client.put(f'{self.base_url}/house/target_temp', json={
            'value': target_temp
        })
        return r.raise_for_status()
