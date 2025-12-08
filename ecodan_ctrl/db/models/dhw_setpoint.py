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
import pytz
from db.base import Model


class DhwSetpoint(Model):
    def __init__(self, setpoint, last_modified=None):
        self.setpoint = round(setpoint, 1)
        self.last_modified = last_modified

    @staticmethod
    def from_naieve_utc(*args, **kwargs):
        def to_localtime(timestamp):
            return timestamp.replace(tzinfo=pytz.utc).astimezone(
                pytz.timezone("Europe/Brussels")
            )

        dhw_setpoint = DhwSetpoint(*args, **kwargs)
        dhw_setpoint.last_modified = to_localtime(dhw_setpoint.last_modified)
        return dhw_setpoint

    @staticmethod
    async def from_db():
        async with Model.db.connect() as conn:
            async with conn.execute(
                "SELECT * FROM dhw_setpoint WHERE zone = ?", ("1",)
            ) as curs:
                result = await curs.fetchone()
                if result:
                    return DhwSetpoint.from_naieve_utc(*result)

    def data(self):
        def to_naieve_utc(timestamp):
            return timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        now = datetime.datetime.now(tz=pytz.timezone("Europe/Brussels"))

        return {"setpoint": self.setpoint, "last_modified": to_naieve_utc(now)}

    async def save(self):
        async with self.db.connect() as conn:
            await conn.execute(
                """INSERT INTO dhw_setpoint VALUES (
                    '1', :setpoint, :last_modified
                )
                ON CONFLICT (zone) DO UPDATE SET
                    setpoint = excluded.setpoint,
                    last_modified = excluded.last_modified
                """,
                self.data(),
            )
            await conn.commit()

    def equals(self, value):
        return int(self.setpoint * 100) == int(value * 100)
