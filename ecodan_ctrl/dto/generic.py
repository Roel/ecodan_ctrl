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


@dataclass
class TimeDataDto:
    timestamp: datetime.datetime
    value: float
    unit: str

    @staticmethod
    def from_json(json):
        return TimeDataDto(
            timestamp=datetime.datetime.fromisoformat(json['timestamp']),
            value=json['value'],
            unit=json['unit']
        )


@dataclass
class TimePeriodStatsDto:
    start: datetime.datetime
    end: datetime.datetime
    unit: str
    q25: float
    q50: float
    q75: float
    stddev: float

    @staticmethod
    def from_json(json):
        return TimePeriodStatsDto(
            start=datetime.datetime.fromisoformat(json['start']),
            end=datetime.datetime.fromisoformat(json['end']),
            unit=json['unit'],
            q25=json['q25'],
            q50=json['q50'],
            q75=json['q75'],
            stddev=json['stddev']
        )


@dataclass
class TimestampDto:
    timestamp: datetime.datetime

    @staticmethod
    def from_isoformat(str):
        return TimestampDto(
            timestamp=datetime.datetime.fromisoformat(str)
        )


@dataclass
class TimeRangeDto:
    start: datetime.datetime
    end: datetime.datetime

    @staticmethod
    def from_json(json):
        return TimeRangeDto(
            start=datetime.datetime.fromisoformat(json['start']),
            end=datetime.datetime.fromisoformat(json['end'])
        )
