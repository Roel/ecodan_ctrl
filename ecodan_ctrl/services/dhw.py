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
import datetime

import math
import pytz

from db.models.dhw_schedule import DhwSchedule
from db.models.operating_mode import Circuit, DhwMode, OperatingMode, DhwRunningMode
from db.models.dhw_setpoint import DhwSetpoint
from errors.dhw import MaxRetriesExceededError


class DhwService:
    def __init__(self, app):
        self.app = app

        self.runtime_hours = self.app.config['DHW_NORMAL_RUNTIME_HOURS']
        self.runtime = datetime.timedelta(hours=self.runtime_hours)

        self.min_interval = datetime.timedelta(
            minutes=self.app.config['DHW_MIN_INTERVAL_MINUTES']
        )

        self.min_interval_retry = datetime.timedelta(
            minutes=self.app.config['DHW_MIN_INTERVAL_RETRY_MINUTES']
        )

        self.max_interval_hours = self.app.config['DHW_NORMAL_INTERVAL_MAX_HOURS']
        self.max_interval = datetime.timedelta(hours=self.max_interval_hours)

        self.max_retry = self.app.config['DHW_MAX_RETRY']

        self.running_mode = DhwRunningMode(self.app.config["DHW_RUNNING_MODE"])

        self.dhw_temp_off = self.app.config['DHW_TEMP_OFF']
        self.dhw_temp_base = self.app.config['DHW_TEMP_BASE']
        self.dhw_temp_buffer_max = self.app.config["DHW_TEMP_BUFFER"]
        self.dhw_temp_drop = self.app.config['DHW_TEMP_DROP']
        self.dhw_temp_drop_ecodan = self.app.config['DHW_TEMP_DROP_ECODAN']

        self.legionella_temp_min_start = self.app.config['DHW_TEMP_LEGIONELLA'] - \
            self.dhw_temp_drop_ecodan

        self.force_legionella_min_temp = self.app.config['HEATING_FADE_MIN_NEXTDAY_TEMP']

        self.buffer_interval = 2
        self.buffer_power_stack = []
        self.buffer_power_stack_size = 8

        self.consumption_kwh = self.app.config['DHW_NORMAL_KWH']

        self.__scheduled_jobs()

    async def plan(self):
        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        self.app.log.debug('Planning DHW cycle')

        operating_mode = await OperatingMode.from_circuit('dhw')
        if operating_mode.mode in [DhwMode.PENDING_NORMAL, DhwMode.RUNNING_NORMAL, DhwMode.RUNNING_BUFFER,
                                   DhwMode.PENDING_LEGIONELLA, DhwMode.RUNNING_LEGIONELLA]:
            # already running
            self.app.log.debug('Already running, not planning.')
            return

        current_schedule = await DhwSchedule.from_mode('dhw')
        if current_schedule and current_schedule.planned_start >= now:
            # already planned
            self.app.log.debug('Already planned, not replanning.')
            return

        current_temp = await self.app.clients.hab.get_current_dhw_temp()
        if current_temp.value > self.dhw_temp_base - self.dhw_temp_drop:
            # still hot enough
            self.app.log.debug(
                'DHW above threshold temperature, not planning.')
            return

        first_start = now + self.min_interval
        ultimate_start = now + self.max_interval - self.runtime

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=first_start,
            end=ultimate_start,
            min_kwh=3,
            peak_duration_h=self.runtime_hours,
            order='first'
        )).timestamp

        self.app.log.debug(f'''Saving new schedule. First start: {first_start},
                           planned start: {planned_start},
                           ultimate_start: {ultimate_start}''')

        new_schedule = DhwSchedule(
            mode='dhw',
            first_start=first_start,
            planned_start=planned_start,
            ultimate_start=ultimate_start,
            fast=True,
            retry=0
        )
        await new_schedule.save()

    async def reschedule(self):
        current_schedule = await DhwSchedule.from_mode('dhw')
        if current_schedule is None:
            return

        current_temp = await self.app.clients.hab.get_current_dhw_temp()
        if current_temp.value > self.dhw_temp_base - self.dhw_temp_drop:
            # hot enough for some reason (triggered manually?)
            self.app.log.debug(
                'DHW above threshold temperature, removing schedule.')
            await current_schedule.remove()
            return

        self.app.log.debug('Rescheduling DHW cycle')

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=current_schedule.first_start,
            end=current_schedule.ultimate_start,
            min_kwh=3,
            peak_duration_h=self.runtime_hours,
            order='first'
        )).timestamp

        if planned_start >= now + self.min_interval:
            self.app.log.debug(
                f'Rescheduled to planned_start: {planned_start}')
            current_schedule.planned_start = planned_start
            await current_schedule.save()
        else:
            self.app.log.debug(
                f'Newly planned_start of {planned_start} is too close to current time, not rescheduling.')

    async def postpone(self):
        current_schedule = await DhwSchedule.from_mode('dhw')
        if current_schedule is None:
            return

        self.app.log.debug('Postponing DHW cycle')

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        if current_schedule.retry >= self.max_retry:
            self.app.log.debug('We are already at maximum number of retries.')
            raise MaxRetriesExceededError

        first_start = max(
            now + self.min_interval_retry,
            current_schedule.first_start
        )

        if first_start >= current_schedule.ultimate_start:
            self.app.log.debug('First start would be after ultimate start.')
            raise MaxRetriesExceededError

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=first_start,
            end=current_schedule.ultimate_start,
            min_kwh=3,
            peak_duration_h=self.runtime_hours,
            order='first'
        )).timestamp

        self.app.log.debug(f'''Postponing (retry {current_schedule.retry + 1})
                           First start: {first_start},
                           planned start: {planned_start},
                           ultimate_start: {current_schedule.ultimate_start}''')

        current_schedule.first_start = first_start
        current_schedule.planned_start = planned_start
        current_schedule.retry = current_schedule.retry + 1
        await current_schedule.save()

    async def start(self):
        operating_mode = await OperatingMode.from_circuit('dhw')
        if operating_mode.mode in [
            DhwMode.PENDING_NORMAL,
            DhwMode.RUNNING_NORMAL,
            DhwMode.RUNNING_STEPPED,
            DhwMode.RUNNING_BUFFER,
        ]:
            return

        self.app.log.debug('Starting DHW cycle')

        can_start, next_legionella = await asyncio.gather(
            self.app.services.controller.can_start(),
            DhwSchedule.from_mode('legionella')
        )

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        if next_legionella is not None and next_legionella.planned_start <= now + self.runtime + (4 * self.min_interval):
            self.app.log.debug(
                f'Will not start DHW cycle, Legionella cycle is due soon at {next_legionella.planned_start}')

            self.app.log.debug('Removing DHW schedule.')
            schedule = await DhwSchedule.from_mode('dhw')
            await schedule.remove()
            return

        if not can_start:
            self.app.log.debug('Cannot start DHW cycle.')
            try:
                await self.postpone()
            except MaxRetriesExceededError:
                # start anyway
                self.app.log.debug('Cannot postpone anymore, starting anyway.')
                pass
            else:
                return

        if self.running_mode == DhwRunningMode.NORMAL:
            dhw_target_setpoint = DhwSetpoint("target", self.dhw_temp_base)

            await asyncio.gather(
                dhw_target_setpoint.save(),
                self.app.clients.ecodan.set_dhw_target_temp(
                    dhw_target_setpoint.setpoint
                ),
            )
        elif self.running_mode == DhwRunningMode.STEPPED:
            dhw_temp = await self.app.clients.hab.get_current_dhw_temp()

            dhw_setpoint = DhwSetpoint(
                "current", math.ceil(dhw_temp.value + self.dhw_temp_drop_ecodan + 1)
            )

            dhw_target_setpoint = DhwSetpoint("target", self.dhw_temp_base)

            await asyncio.gather(
                dhw_setpoint.save(),
                dhw_target_setpoint.save(),
                self.app.clients.ecodan.set_dhw_target_temp(dhw_setpoint.setpoint),
            )

        self.app.log.debug(
            f'Setting {Circuit.DHW} to mode: {DhwMode.PENDING_NORMAL}')
        operating_mode.mode = DhwMode.PENDING_NORMAL
        await operating_mode.save()

        self.app.log.debug('Removing DHW schedule.')
        schedule = await DhwSchedule.from_mode('dhw')
        await schedule.remove()

    async def step(self):
        if self.running_mode != DhwRunningMode.STEPPED:
            return

        operating_mode = await OperatingMode.from_circuit("dhw")
        if operating_mode.mode not in [DhwMode.RUNNING_NORMAL, DhwMode.RUNNING_STEPPED]:
            return

        dhw_temp, dhw_setpoint, dhw_target_setpoint = await asyncio.gather(
            self.app.clients.hab.get_current_dhw_temp(),
            DhwSetpoint.from_type("current"),
            DhwSetpoint.from_type("target"),
        )

        if operating_mode.mode == DhwMode.RUNNING_NORMAL:
            if dhw_temp.value < dhw_setpoint.setpoint - self.buffer_interval:
                # not hot enough
                self.app.log.debug(
                    f"Still heating up (now: {dhw_temp.value}) to normal temperature, not enabling stepping mode."
                )
                return
            else:
                self.app.log.debug("Enabling DHW stepping mode.")
                self.app.log.debug(
                    f"Setting {Circuit.DHW} to mode: {DhwMode.RUNNING_STEPPED}"
                )
                operating_mode.mode = DhwMode.RUNNING_STEPPED
                await operating_mode.save()

        if operating_mode.mode == DhwMode.RUNNING_STEPPED:
            if dhw_temp.value >= dhw_setpoint.setpoint - self.buffer_interval:
                if dhw_setpoint.setpoint <= dhw_target_setpoint.setpoint - 1:
                    self.app.log.debug(
                        f"""Current DHW temperature of {dhw_temp.value}° is within {self.buffer_interval}° of current target.
                        Setting target to {dhw_setpoint.setpoint + 1}°."""
                    )
                    dhw_setpoint.setpoint += 1
                    await asyncio.gather(
                        dhw_setpoint.save(),
                        self.app.clients.ecodan.set_dhw_target_temp(
                            dhw_setpoint.setpoint
                        ),
                    )
                else:
                    self.app.log.debug(
                        f"""Current DHW temperature of {dhw_temp.value}° is not yet within {self.buffer_interval}° of current target.
                        Not increasing target yet."""
                    )
            else:
                self.app.log.debug(
                    f"""Current DHW temperature of {dhw_temp.value}° is lower than or equal to 
                        {dhw_setpoint.setpoint - self.buffer_interval}°, nothing to do."""
                )

    async def buffer(self):
        operating_mode = await OperatingMode.from_circuit("dhw")
        if operating_mode.mode not in [
            DhwMode.RUNNING_NORMAL,
            DhwMode.RUNNING_STEPPED,
            DhwMode.RUNNING_BUFFER,
        ]:
            return

        current_net_power, heatpump_status, dhw_temp, dhw_setpoint, next_legionella = (
            await asyncio.gather(
                self.app.clients.hab.get_current_net_power(),
                self.app.clients.hab.get_current_state(),
                self.app.clients.hab.get_current_dhw_temp(),
                DhwSetpoint.from_type("current"),
                DhwSchedule.from_mode("legionella"),
            )
        )

        if next_legionella is not None:
            next_legionella_outdoor_temp = (
                await self.app.clients.mme_soleil.get_temperature_stats(
                    next_legionella.planned_start,
                    next_legionella.planned_start + datetime.timedelta(hours=2),
                )
            )
        else:
            next_legionella_outdoor_temp = None

        now = datetime.datetime.now(tz=pytz.timezone("Europe/Brussels"))

        if operating_mode.mode in (DhwMode.RUNNING_NORMAL, DhwMode.RUNNING_STEPPED):
            if dhw_temp.value < dhw_setpoint.setpoint - self.buffer_interval:
                # not hot enough
                self.app.log.debug(
                    f"Still heating up (now: {dhw_temp.value}) to normal temperature, not enabling buffer mode."
                )
                return
            elif (
                heatpump_status.heat_source == "Heatpump"
                and current_net_power.value < 0
            ):
                # enable buffer mode
                self.app.log.debug("Enabling DHW buffer mode.")
                self.app.log.debug(
                    f"Setting {Circuit.DHW} to mode: {DhwMode.RUNNING_BUFFER}"
                )
                self.buffer_power_stack.clear()
                operating_mode.mode = DhwMode.RUNNING_BUFFER
                await operating_mode.save()
            else:
                # not enabling buffer mode
                self.app.log.debug(
                    f"Not enabling DHW buffer mode: heatsource is {heatpump_status.heat_source} and "
                    f"current net power is {current_net_power.value}."
                )

        if operating_mode.mode == DhwMode.RUNNING_BUFFER:
            if (
                dhw_temp.value >= self.legionella_temp_min_start
                and next_legionella is not None
                and next_legionella_outdoor_temp is not None
                and (
                    next_legionella.planned_start
                    <= now + self.runtime + (16 * self.min_interval)
                    or next_legionella_outdoor_temp.q50
                    <= self.force_legionella_min_temp
                )
            ):
                self.app.log.debug(
                    f"Legionella cycle was planned soon at {next_legionella.planned_start}, starting already."
                )
                await self.app.services.legionella.start(force_start=True)
                dhw_setpoint = DhwSetpoint("current", 0 + self.dhw_temp_base)
                await dhw_setpoint.save()
                return

            if (
                heatpump_status.heat_source != "Heatpump"
                and heatpump_status.defrost_status == "Normal"
            ):
                # using booster, stop
                self.app.log.debug(
                    f"Stopping DHW buffer mode: heatsource is {heatpump_status.heat_source}"
                )
                await self.stop_buffer()
                return

            self._update_buffer_power_stack(current_net_power.value)
            if not self._check_buffer_power_stack():
                # drawing power from the net, stopping buffering
                self.app.log.debug(
                    f"Stopping DHW buffer mode: net power draw was {self.buffer_power_stack}"
                )
                await self.stop_buffer()
                self.buffer_power_stack.clear()
                return

            dhw_setpoint = await DhwSetpoint.from_type("current")

            if dhw_temp.value >= dhw_setpoint.setpoint - self.buffer_interval:
                if dhw_setpoint.setpoint <= self.dhw_temp_buffer_max - 1:
                    self.app.log.debug(
                        f"""Current DHW temperature of {dhw_temp.value}° is within {self.buffer_interval}° of current target.
                        Setting target to {dhw_setpoint.setpoint + 1}°."""
                    )
                    dhw_setpoint.setpoint += 1
                    await asyncio.gather(
                        dhw_setpoint.save(),
                        self.app.clients.ecodan.set_dhw_target_temp(
                            dhw_setpoint.setpoint
                        ),
                    )
                else:
                    self.app.log.debug(
                        f"""Current DHW temperature of {dhw_temp.value}° is not yet within {self.buffer_interval}° of current target.
                        Not increasing target yet."""
                    )
            else:
                self.app.log.debug(
                    f"""Current DHW temperature of {dhw_temp.value}° is lower than or equal to 
                        {dhw_setpoint.setpoint - self.buffer_interval}°, nothing to do."""
                )

    async def stop_buffer(self):
        dhw_temp, operating_mode = await asyncio.gather(
            self.app.clients.hab.get_current_dhw_temp(),
            OperatingMode.from_circuit('dhw')
        )

        if dhw_temp.value < self.dhw_temp_base:
            # not hot enough, back to normal mode
            self.app.log.debug(
                f'Current DHW temperature of {dhw_temp.value} is below base temperature of {self.dhw_temp_base}, '
                'switching back to normal operation.')

            await self.app.clients.ecodan.set_dhw_target_temp(self.dhw_temp_base)

            self.app.log.debug(
                f'Setting {Circuit.DHW} to mode: {DhwMode.RUNNING_NORMAL}')
            operating_mode.mode = DhwMode.RUNNING_NORMAL
            await operating_mode.save()

            dhw_setpoint = DhwSetpoint("current", 0 + self.dhw_temp_base)
            await dhw_setpoint.save()
        else:
            # hot enough, time to stop
            await self.stop()

    async def stop(self):
        operating_mode = await OperatingMode.from_circuit('dhw')

        self.app.log.debug('Stopping DHW cycle')

        await self.app.clients.ecodan.set_dhw_target_temp(self.dhw_temp_off)

        self.app.log.debug(f'Setting {Circuit.DHW} to mode: {DhwMode.OFF}')
        operating_mode.mode = DhwMode.OFF
        await operating_mode.save()

        dhw_setpoint = DhwSetpoint("current", 0 + self.dhw_temp_base)
        await dhw_setpoint.save()

    async def update_from_state(self):
        operating_mode, current_state = await asyncio.gather(
            OperatingMode.from_circuit('dhw'),
            self.app.clients.hab.get_current_state()
        )

        if (
            operating_mode.mode == DhwMode.OFF
            and current_state.operating_mode == "Hot water"
        ):
            operating_mode.mode = DhwMode.RUNNING_MANUAL
            await operating_mode.save()
            return

        if (
            operating_mode.mode == DhwMode.RUNNING_MANUAL
            and current_state.operating_mode != "Hot water"
        ):
            operating_mode.mode = DhwMode.OFF
            await operating_mode.save()
            return

        if operating_mode.mode == DhwMode.PENDING_NORMAL:
            if current_state.operating_mode == 'Hot water':
                self.app.log.debug(
                    f'Setting {Circuit.DHW} to mode: {DhwMode.RUNNING_NORMAL}')
                operating_mode.mode = DhwMode.RUNNING_NORMAL
                await operating_mode.save()
        elif operating_mode.mode in [
            DhwMode.RUNNING_NORMAL,
            DhwMode.RUNNING_BUFFER,
            DhwMode.RUNNING_STEPPED,
        ]:
            if current_state.operating_mode != 'Hot water':
                await self.stop()
            else:
                await self.step()
                await self.buffer()

    def _update_buffer_power_stack(self, net_power):
        if len(self.buffer_power_stack) >= self.buffer_power_stack_size:
            self.buffer_power_stack.pop(0)
        self.buffer_power_stack.append(net_power)

    def _check_buffer_power_stack(self):
        # can buffering continue?
        for net_power in self.buffer_power_stack:
            if net_power <= 0:
                return True
        return False

    def __scheduled_jobs(self):
        self.app.scheduler.add_job(self.reschedule, 'cron', minute='54')
