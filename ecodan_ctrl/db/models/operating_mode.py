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
from enum import Enum
import pytz
from db.base import Model


class Circuit(Enum):
    DHW = 'dhw'


class DhwMode(Enum):
    OFF = 'off'
    PENDING_NORMAL = 'pending_normal'
    RUNNING_NORMAL = 'running_normal'
    RUNNING_STEPPED = "running_stepped"
    RUNNING_BUFFER = 'running_buffer'
    PENDING_LEGIONELLA = 'pending_legionella'
    RUNNING_LEGIONELLA = 'running_legionella'


class DhwRunningMode(Enum):
    NORMAL = "normal"
    STEPPED = "stepped"


class OperatingMode(Model):
    def __init__(self, circuit, mode, last_modified=None):
        self.circuit = circuit
        self.mode = mode
        self.last_modified = last_modified

    @staticmethod
    def from_naieve_utc(*args, **kwargs):
        def to_localtime(timestamp):
            return timestamp.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Europe/Brussels'))

        operating_mode = OperatingMode(*args, **kwargs)
        operating_mode.circuit = Circuit(operating_mode.circuit)
        if operating_mode.circuit == Circuit.DHW:
            operating_mode.mode = DhwMode(operating_mode.mode)
        operating_mode.last_modified = to_localtime(
            operating_mode.last_modified)
        return operating_mode

    @staticmethod
    async def from_circuit(circuit):
        async with Model.db.connect() as conn:
            async with conn.execute(
                    'SELECT * FROM operating_mode WHERE circuit = ?', (circuit,)) as curs:
                result = await curs.fetchone()
                if result:
                    return OperatingMode.from_naieve_utc(*result)

    def data(self):
        def to_naieve_utc(timestamp):
            return timestamp.astimezone(pytz.utc).replace(tzinfo=None)

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        return {
            'circuit': self.circuit.value,
            'mode': self.mode.value,
            'last_modified': to_naieve_utc(now)
        }

    async def save(self):
        async with self.db.connect() as conn:
            await conn.execute(
                """INSERT INTO operating_mode VALUES (
                    :circuit, :mode, :last_modified
                )
                ON CONFLICT (circuit) DO UPDATE SET
                    mode = excluded.mode,
                    last_modified = excluded.last_modified
                """, self.data())
            await conn.commit()
