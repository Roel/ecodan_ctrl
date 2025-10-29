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

from dataclasses import dataclass
import datetime
from enum import Enum


@dataclass
class SetpointDto:
    class SetpointType(Enum):
        RAISE = 1
        DROP = 2
        RAISE_BUFFER = 3

    timestamp: datetime.datetime
    setpoint: float
    setpoint_type: SetpointType

    def __init__(self, timestamp, setpoint, setpoint_type):
        self.timestamp = timestamp
        self.setpoint = round(setpoint, 1)
        self.setpoint_type = setpoint_type
