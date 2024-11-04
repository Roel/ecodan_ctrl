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

import pytz
from db.base import Model


class DhwSchedule(Model):
    def __init__(self, mode, first_start, planned_start, ultimate_start, fast=False, retry=0):
        self.mode = mode
        self.first_start = first_start
        self.planned_start = planned_start
        self.ultimate_start = ultimate_start
        self.fast = fast
        self.retry = retry

    @staticmethod
    def from_naieve_utc(*args, **kwargs):
        def to_localtime(timestamp):
            return timestamp.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Europe/Brussels'))

        dhw_schedule = DhwSchedule(*args, **kwargs)
        dhw_schedule.first_start = to_localtime(dhw_schedule.first_start)
        dhw_schedule.planned_start = to_localtime(dhw_schedule.planned_start)
        dhw_schedule.ultimate_start = to_localtime(dhw_schedule.ultimate_start)
        return dhw_schedule

    @staticmethod
    async def from_mode(mode):
        async with Model.db.connect() as conn:
            async with conn.execute(
                    'SELECT * FROM dhw_schedule WHERE mode = ?', (mode,)) as curs:
                result = await curs.fetchone()
                if result:
                    return DhwSchedule.from_naieve_utc(*result)

    def data(self):
        def to_naieve_utc(timestamp):
            return timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        return {
            'mode': self.mode,
            'first_start': to_naieve_utc(self.first_start),
            'planned_start': to_naieve_utc(self.planned_start),
            'ultimate_start': to_naieve_utc(self.ultimate_start),
            'fast': self.fast,
            'retry': self.retry
        }

    @staticmethod
    async def get_next_planned():
        async with Model.db.connect() as conn:
            async with conn.execute(
                    'SELECT * FROM dhw_schedule ORDER BY planned_start LIMIT 1') as curs:
                result = await curs.fetchone()
                if result:
                    return DhwSchedule.from_naieve_utc(*result)

    async def save(self):
        async with self.db.connect() as conn:
            await conn.execute(
                """INSERT INTO dhw_schedule VALUES (
                    :mode, :first_start, :planned_start, :ultimate_start, :fast, :retry
                )
                ON CONFLICT (mode) DO UPDATE SET
                    first_start = excluded.first_start,
                    planned_start = excluded.planned_start,
                    ultimate_start = excluded.ultimate_start,
                    fast = excluded.fast,
                    retry = excluded.retry
                """, self.data())
            await conn.commit()

    async def remove(self):
        async with self.db.connect() as conn:
            await conn.execute('DELETE FROM dhw_schedule WHERE mode = ?', (self.mode,))
            await conn.commit()
