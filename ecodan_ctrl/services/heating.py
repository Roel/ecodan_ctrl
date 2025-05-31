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

import asyncio
from dataclasses import dataclass
import datetime
from enum import Enum

import pytz

from db.models.heating_setpoint import HeatingSetpoint
from db.models.operating_mode import DhwMode, OperatingMode


@dataclass
class SetpointDto:
    class SetpointType(Enum):
        RAISE = 1
        DROP = 2
        RAISE_BUFFER = 3

    timestamp: datetime.datetime
    setpoint: float
    setpoint_type: SetpointType


class HeatingService:
    def __init__(self, app):
        self.app = app

        self.temp_min = self.app.config['HEATING_TEMP_MIN']
        self.temp_night = self.app.config['HEATING_TEMP_NIGHT']
        self.temp_day = self.app.config['HEATING_TEMP_DAY']

        self.buffer_min_clearsky_ratio = self.app.config['HEATING_BUFFER_MIN_CLEARSKY_RATIO']
        self.buffer_min_production_w = self.app.config['HEATING_BUFFER_MIN_PRODUCTION_W']
        self.buffer_min_production_hours = self.app.config['HEATING_BUFFER_MIN_PRODUCTION_HOURS']
        self.buffer_min_prediction_ratio = self.app.config['HEATING_BUFFER_MIN_PREDICTION_RATIO']
        self.buffer_temp_added = self.app.config['HEATING_BUFFER_TEMP_ADDED']
        self.buffer_max_temp_night = self.app.config['HEATING_BUFFER_MAX_TEMP_NIGHT']

        self.fade_min_temp_night = self.app.config['HEATING_FADE_MIN_TEMP_NIGHT']
        self.fade_min_temp_force_off = self.app.config['HEATING_FADE_MIN_TEMP_FORCE_OFF']
        self.fade_min_clearsky_ratio = self.app.config['HEATING_FADE_MIN_CLEARSKY_RATIO']
        self.fade_min_nextday_temp = self.app.config['HEATING_FADE_MIN_NEXTDAY_TEMP']

        self.summer_mode_min_outside = self.app.config['HEATING_SUMMER_MODE_MIN_OUTSIDE']
        self.summer_mode_min_inside = self.app.config['HEATING_SUMMER_MODE_MIN_INSIDE']
        self.summer_mode_temp = self.app.config['HEATING_SUMMER_MODE_TEMP']

        self.fade_period = datetime.timedelta(
            hours=self.app.config['HEATING_FADE_PERIOD_HOURS'])
        self.fade_steps = self.app.config['HEATING_FADE_STEPS']

        fade_during = self.app.config['HEATING_FADE_DURING'].lower()
        if fade_during == 'day':
            self.fade_offset_sunrise = datetime.timedelta(seconds=0)
            self.fade_offset_sunset = self.fade_period
        elif fade_during == 'night':
            self.fade_offset_sunrise = self.fade_period
            self.fade_offset_sunset = datetime.timedelta(seconds=0)
        elif fade_during == 'dusk':
            self.fade_offset_sunrise = self.fade_period / 2
            self.fade_offset_sunset = self.fade_period / 2
        else:
            raise ValueError(
                'Invalid setting for HEATING_FADE_DURING: should be day, night, or dusk.')

        self.heating_plan = []
        self.in_idle_state_since = None

        self.__scheduled_jobs()

    async def plan_summer_mode(self):
        today_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(0, 0, 0))
        )

        tomorrow_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(10, 0, 0))
        )

        tomorrow_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(19, 59, 59))
        )

        tomorrow_plus1_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=2),
                datetime.time(10, 0, 0))
        )

        tomorrow_plus1_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=2),
                datetime.time(19, 59, 59))
        )

        tomorrow_temp, tomorrow_plus1_temp, inside_temp = await asyncio.gather(
            self.app.clients.mme_soleil.get_temperature_stats(
                tomorrow_start, tomorrow_end),
            self.app.clients.mme_soleil.get_temperature_stats(
                tomorrow_plus1_start, tomorrow_plus1_end),
            self.app.clients.hab.get_house_temperature()
        )

        outside_temp = (tomorrow_temp.q75 + tomorrow_plus1_temp.q75) / 2
        if outside_temp >= self.summer_mode_min_outside and inside_temp.q50 >= self.summer_mode_min_inside:
            self.app.log.debug(
                f'Average outside temp of {outside_temp} is greater than or equal to {self.summer_mode_min_outside} '
                f'and internal temp of {inside_temp.q50} is greater than or equal to {self.summer_mode_min_inside}: '
                f'enabling summer mode.')

            # summer mode is on
            return [SetpointDto(
                timestamp=today_start, setpoint=self.summer_mode_temp,
                setpoint_type=SetpointDto.SetpointType.DROP)]
        else:
            self.app.log.debug(
                f'Average outside temp of {outside_temp} lower than {self.summer_mode_min_outside} '
                f'or internal temp of {inside_temp.q50} is lower than {self.summer_mode_min_inside}: '
                f'not enabling summer mode.')

    async def plan(self):
        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        summer_mode_schedule = await self.plan_summer_mode()
        if summer_mode_schedule is not None:
            self.heating_plan = summer_mode_schedule
            return

        today_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(0, 0, 0))
        )

        today_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(23, 59, 59))
        )

        tomorrow_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(0, 0, 0))
        )

        tomorrow_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(23, 59, 59))
        )

        tomorrow_day_start = tomorrow_start.replace(hour=8)
        tomorrow_day_end = tomorrow_start.replace(hour=20)

        night_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(20, 0, 0))
        )

        night_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(8, 0, 0))
        )

        production_bounds, night_temp, tomorrow_day_temp, tomorrows_production, todays_production, heatpump_setpoint = await asyncio.gather(
            self.app.clients.mme_soleil.get_production_bounds(),
            self.app.clients.mme_soleil.get_temperature_stats(
                night_start, night_end),
            self.app.clients.mme_soleil.get_temperature_stats(
                tomorrow_day_start, tomorrow_day_end),
            self.app.clients.mme_soleil.get_production_weather(
                tomorrow_start, tomorrow_end),
            self.app.clients.mme_soleil.get_production_weather(
                today_start, today_end),
            self.app.clients.hab.get_setpoint()
        )

        self.app.log.debug('Planning heating schedule.')

        self.app.log.debug(
            f'Production today will start at {production_bounds.start} and end at {production_bounds.end}.')

        heat_raise_start = production_bounds.start - self.fade_offset_sunrise
        heat_drop_start = production_bounds.end - self.fade_offset_sunset

        temp_night = min(self.temp_night, heatpump_setpoint.heating)

        step_temp = (self.temp_day - temp_night) / self.fade_steps
        step_interval = self.fade_period / self.fade_steps

        datapoints = []

        self.app.log.debug(f'Heat buildup will start at {heat_raise_start}.')

        datapoints.append(SetpointDto(
            timestamp=heat_raise_start, setpoint=temp_night, setpoint_type=SetpointDto.SetpointType.RAISE))

        for i in range(self.fade_steps):
            datapoints.append(SetpointDto(
                timestamp=heat_raise_start + ((i+1) * step_interval),
                setpoint=datapoints[-1].setpoint + step_temp,
                setpoint_type=SetpointDto.SetpointType.RAISE
            ))

        if night_temp.q50 <= self.fade_min_temp_force_off:
            # too cold, don't drop
            drop_night_temp = False

            self.app.log.debug(
                f'Expected median night temperature of {round(night_temp.q50, 2)} is equal to or below '
                f'threshold of {self.fade_min_temp_force_off}, '
                f'forced to keep setpoint at {self.temp_day} tonight.')

        elif night_temp.q50 <= self.fade_min_temp_night:
            # between force on and force off

            if tomorrows_production.ratio >= self.fade_min_clearsky_ratio:
                # tomorrow sunny, drop
                drop_night_temp = True

                self.app.log.debug(
                    f'Expected median night temperature of {round(night_temp.q50, 2)} is equal to or below '
                    f'threshold of {self.fade_min_temp_night}, '
                    f'but tomorrow will be sunny '
                    f'(clearsky ratio: {round(tomorrows_production.ratio, 2)} >= {self.fade_min_clearsky_ratio}), '
                    f'dropping setpoint to {self.temp_night} tonight.')

            elif tomorrow_day_temp.q50 >= self.fade_min_nextday_temp:
                # tomorrow warm, drop
                drop_night_temp = True

                self.app.log.debug(
                    f'Expected median night temperature of {round(night_temp.q50, 2)} is equal to or below '
                    f'threshold of {self.fade_min_temp_night}, '
                    f'but tomorrow will be warm '
                    f'({round(tomorrow_day_temp.q50, 2)} >= {self.fade_min_nextday_temp}), '
                    f'dropping setpoint to {self.temp_night} tonight.')

            else:
                # tomorrow cold and cloudy, don't drop
                drop_night_temp = False

                self.app.log.debug(
                    f'Expected median night temperature of {round(night_temp.q50, 2)} is equal to or below '
                    f'threshold of {self.fade_min_temp_night}, '
                    f'keeping setpoint at {self.temp_day} tonight.')

        elif night_temp.q50 >= self.fade_min_nextday_temp:
            # warm enough tonight

            if tomorrow_day_temp.q50 <= self.fade_min_temp_night:
                # tomorrow cold, don't drop
                drop_night_temp = False

                self.app.log.debug(
                    f'Expected median night temperature of {round(night_temp.q50, 2)} is above '
                    f'threshold of {self.fade_min_temp_night}, '
                    f'but tomorrow will be cold '
                    f'({round(tomorrow_day_temp.q50, 2)} <= {self.fade_min_temp_night}), '
                    f'keeping setpoint at {self.temp_day} tonight.')
            else:
                # tomorrow warm, drop
                drop_night_temp = True

                self.app.log.debug(
                    f'Expected median night temperature of {round(night_temp.q50, 2)} is above '
                    f'threshold of {self.fade_min_temp_night}, '
                    f'dropping setpoint to {self.temp_night} tonight.')
        else:
            drop_night_temp = True

            self.app.log.debug(
                f'Expected median night temperature of {round(night_temp.q50, 2)} is above '
                f'threshold of {self.fade_min_temp_night}, '
                f'dropping setpoint to {self.temp_night} tonight.')

        if drop_night_temp:
            datapoints.append(SetpointDto(
                timestamp=heat_drop_start, setpoint=self.temp_day, setpoint_type=SetpointDto.SetpointType.DROP))

            for i in range(self.fade_steps):
                datapoints.append(SetpointDto(
                    timestamp=heat_drop_start + ((i+1) * step_interval),
                    setpoint=datapoints[-1].setpoint - step_temp,
                    setpoint_type=SetpointDto.SetpointType.DROP
                ))

        fade_offset = self.fade_period / 4
        step_temp = self.buffer_temp_added / self.fade_steps
        step_interval = self.fade_period / self.fade_steps

        buffer_bounds = await self.app.clients.mme_soleil.get_production_bounds(
            min_kw=self.buffer_min_production_w/1000)

        # always drop buffer
        if buffer_bounds is None or buffer_bounds.end is None:
            buffer_drop_start = now
        else:
            buffer_drop_start = buffer_bounds.end - fade_offset

        if todays_production.ratio >= self.buffer_min_clearsky_ratio and night_temp.q50 <= self.buffer_max_temp_night:

            if buffer_bounds.start is not None \
                    and buffer_bounds.end is not None \
                    and buffer_bounds.end - buffer_bounds.start >= datetime.timedelta(
                        hours=self.buffer_min_production_hours):

                # enable heat buffer
                self.app.log.debug(
                    f'Expect a sunny day today, and a cold night tonight, enabling heat buffer mode.'
                )

                buffer_raise_start = buffer_bounds.start - fade_offset

                self.app.log.debug(
                    f'Buffering will occur between {buffer_raise_start} and {buffer_drop_start}.')

                for i in range(self.fade_steps):
                    datapoints.append(SetpointDto(
                        timestamp=buffer_raise_start + ((i+1) * step_interval),
                        setpoint=self.temp_day + ((i+1) * step_temp),
                        setpoint_type=SetpointDto.SetpointType.RAISE_BUFFER
                    ))

        for i in range(self.fade_steps):
            datapoints.append(SetpointDto(
                timestamp=buffer_drop_start + ((i+1) * step_interval),
                setpoint=self.temp_day +
                self.buffer_temp_added - ((i+1) * step_temp),
                setpoint_type=SetpointDto.SetpointType.DROP
            ))

        self.heating_plan = datapoints

    def get_current_setpoint(self):
        heating_plan = sorted(self.heating_plan, key=lambda sp: sp.timestamp)

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))
        past_setpoints = [sp for sp in heating_plan if sp.timestamp <= now]

        if len(past_setpoints) > 0:
            return past_setpoints[-1]
        else:
            return None

    async def evaluate(self):
        current_setpoint = self.get_current_setpoint()
        if current_setpoint is None:
            self.app.log.debug('No heating setpoint in plan.')
            await self.plan()
            return

        state_setpoint, heatpump_setpoint = await asyncio.gather(
            HeatingSetpoint.from_zone('zone1'),
            self.app.clients.hab.get_setpoint()
        )

        heatpump_setpoint = heatpump_setpoint.heating

        if state_setpoint is None:
            state_setpoint = HeatingSetpoint('zone1', heatpump_setpoint)

        if not state_setpoint.equals(current_setpoint.setpoint):
            if current_setpoint.setpoint_type == SetpointDto.SetpointType.RAISE_BUFFER:
                if not await self.can_start_buffer():
                    return

            self.app.log.debug(
                f'State setpoint of {state_setpoint.setpoint} differs from current target setpoint '
                f'of {current_setpoint.setpoint}.')

            if current_setpoint.setpoint_type in (SetpointDto.SetpointType.RAISE, SetpointDto.SetpointType.RAISE_BUFFER):
                if current_setpoint.setpoint <= heatpump_setpoint:
                    self.app.log.debug(
                        'Not lowering setpoint during heat raise.')
                    return

            if current_setpoint.setpoint_type == SetpointDto.SetpointType.DROP:
                if current_setpoint.setpoint >= heatpump_setpoint:
                    self.app.log.debug(
                        'Not raising setpoint during heat drop.')
                    return

            await self.app.clients.ecodan.set_heating_target_temp(current_setpoint.setpoint)
            state_setpoint.setpoint = current_setpoint.setpoint
            await state_setpoint.save()

    async def check_idling(self):
        heatpump_state, heatpump_setpoint, dhw_mode, = await asyncio.gather(
            self.app.clients.hab.get_current_state(),
            self.app.clients.hab.get_setpoint(),
            OperatingMode.from_circuit('dhw')
        )

        if dhw_mode.mode != DhwMode.OFF:
            # in DHW mode, not interfering
            return

        if heatpump_state.defrost_status != 'Normal':
            # in defrost, not interfering
            return

        if heatpump_state.operating_mode != 'Stop' and heatpump_state.heat_source == 'Heatpump pause':
            # in idle state
            now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

            if self.in_idle_state_since is None:
                self.app.log.debug('Detected heatpump in idle state.')
                self.in_idle_state_since = now
            elif self.in_idle_state_since <= now - datetime.timedelta(minutes=9):
                # already more than 9 minutes in idle state, drop temperature

                if heatpump_setpoint.heating > self.temp_min:
                    new_setpoint = heatpump_setpoint.heating - 0.5

                    self.app.log.debug(
                        f'Detected heatpump in idle state since {self.in_idle_state_since}, dropping temperature '
                        f'to {new_setpoint}.')

                    self.heating_plan.append(
                        SetpointDto(
                            timestamp=now,
                            setpoint=new_setpoint,
                            setpoint_type=SetpointDto.SetpointType.DROP
                        )
                    )
        else:
            # not in idle state, reset
            self.in_idle_state_since = None

    async def can_start_buffer(self):
        today_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(0, 0, 0))
        )

        today_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(23, 59, 59))
        )

        night_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today(),
                datetime.time(20, 0, 0))
        )

        night_end = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1),
                datetime.time(8, 0, 0))
        )

        night_temp, todays_production = await asyncio.gather(
            self.app.clients.mme_soleil.get_temperature_stats(
                night_start, night_end),
            self.app.clients.mme_soleil.get_production_weather(
                today_start, today_end)
        )

        if todays_production.ratio < self.buffer_min_clearsky_ratio or night_temp.q50 > self.buffer_max_temp_night:
            return False

        current_net_power, daily_production = await asyncio.gather(
            self.app.clients.hab.get_current_net_power(),
            self.app.clients.hab.get_daily_production()
        )

        daily_prediction = await self.app.clients.mme_soleil.get_daily_production(end_time=daily_production.timestamp)

        if daily_production.value/daily_prediction.value < self.buffer_min_prediction_ratio:
            return False

        return current_net_power.value < self.buffer_min_production_w * -0.5

    async def update_from_state(self):
        heatpump_setpoint = await self.app.clients.hab.get_setpoint()

        self.app.log.debug(
            f'Setting heating state setpoint from heatpump state, to a value of {heatpump_setpoint.heating}.')
        state_setpoint = HeatingSetpoint('zone1', heatpump_setpoint.heating)
        await state_setpoint.save()

    def __scheduled_jobs(self):
        self.app.scheduler.add_job(self.plan, 'cron', hour='4', minute='10')
        self.app.scheduler.add_job(self.plan, 'cron', hour='13', minute='10')
        self.app.scheduler.add_job(self.check_idling, 'cron', minute='*/5')
