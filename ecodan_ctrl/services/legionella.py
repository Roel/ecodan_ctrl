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


class LegionellaService:
    def __init__(self, app):
        self.app = app

        self.interval = datetime.timedelta(
            days=self.app.config['DHW_LEGIONELLA_INTERVAL_DAYS'])

        self.min_interval = datetime.timedelta(
            days=self.app.config['DHW_LEGIONELLA_MIN_INTERVAL_DAYS'])

        self.min_start_interval = datetime.timedelta(
            minutes=self.app.config['DHW_MIN_INTERVAL_MINUTES']
        )

        self.min_start_interval_retry = datetime.timedelta(
            minutes=self.app.config['DHW_MIN_INTERVAL_RETRY_MINUTES']
        )

        self.runtime_hours = self.app.config['DHW_LEGIONELLA_RUNTIME_HOURS']
        self.runtime = datetime.timedelta(hours=self.runtime_hours)

        self.max_runtime_hours_ecodan = self.app.config["DHW_ECODAN_MAX_RUNTIME_HOURS"]
        self.max_runtime_ecodan = datetime.timedelta(
            hours=self.max_runtime_hours_ecodan
        )

        self.max_retry = self.app.config['DHW_MAX_RETRY']

        self.running_mode = DhwRunningMode(self.app.config["DHW_RUNNING_MODE"])
        self.running_mode_stepped_max_temp = self.app.config[
            "DHW_RUNNING_MODE_AUTO_STEP_MAX_TEMP"
        ]

        self.dhw_temp_off = self.app.config['DHW_TEMP_OFF']
        self.dhw_temp_legionella = self.app.config['DHW_TEMP_LEGIONELLA']
        self.dhw_temp_drop = self.app.config['DHW_TEMP_DROP']
        self.dhw_temp_drop_ecodan = self.app.config['DHW_TEMP_DROP_ECODAN']

        self.legionella_temp_min_start = self.dhw_temp_legionella - self.dhw_temp_drop_ecodan

        self.consumption_kwh = self.app.config['DHW_LEGIONELLA_KWH']

        self.buffer_interval = 2

        # fallback
        self.timestamp_started = datetime.datetime.now(
            tz=pytz.timezone("Europe/Brussels")
        )

        self.__scheduled_jobs()

    async def plan(self):
        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        self.app.log.debug('Planning Legionella cycle')

        current_schedule, operating_mode = await asyncio.gather(
            DhwSchedule.from_mode('legionella'),
            OperatingMode.from_circuit('dhw')
        )

        if current_schedule and current_schedule.planned_start >= now:
            # already planned
            self.app.log.debug('Already planned, not replanning.')
            return

        if operating_mode and operating_mode.mode in [DhwMode.PENDING_LEGIONELLA, DhwMode.RUNNING_LEGIONELLA]:
            # already started
            self.app.log.debug('Already started, not planning.')
            return

        last_start = (await self.app.clients.hab.get_last_legionella_start()).timestamp
        ultimate_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                (last_start + self.interval).date(),
                datetime.time(23, 59, 59)
            )
        )
        order = 'last'

        if ultimate_start <= now:
            ultimate_start = pytz.timezone('Europe/Brussels').localize(
                datetime.datetime.combine(
                    datetime.datetime.today() + datetime.timedelta(days=1),
                    datetime.time(23, 59, 59)
                )
            )
            order = 'first'

        first_start = max(
            ultimate_start - (self.interval - self.min_interval),
            now + self.min_start_interval
        )

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=first_start,
            end=ultimate_start,
            min_kwh=self.consumption_kwh,
            peak_duration_h=self.runtime_hours,
            order=order
        )).timestamp

        self.app.log.debug(f'''Saving new schedule. First start: {first_start},
                           planned start: {planned_start},
                           ultimate_start: {ultimate_start}''')

        new_schedule = DhwSchedule(
            mode='legionella',
            first_start=first_start,
            planned_start=planned_start,
            ultimate_start=ultimate_start,
            fast=(order == 'first'),
            retry=0
        )
        await new_schedule.save()

    async def reschedule(self):
        current_schedule = await DhwSchedule.from_mode('legionella')
        if current_schedule is None:
            return

        self.app.log.debug('Rescheduling Legionella cycle')

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        last_start = (await self.app.clients.hab.get_last_legionella_start()).timestamp
        new_ultimate_start = pytz.timezone('Europe/Brussels').localize(
            datetime.datetime.combine(
                (last_start + self.interval).date(),
                datetime.time(23, 59, 59)
            )
        )

        if new_ultimate_start > current_schedule.ultimate_start:
            self.app.log.debug(
                f'''Ultimate start {new_ultimate_start} is after current ultimate start
                of {current_schedule.ultimate_start}, rescheduling beyond ultimate start.''')
            ultimate_start = new_ultimate_start
            first_start = max(
                ultimate_start - (self.interval - self.min_interval),
                now + self.min_start_interval
            )
        else:
            ultimate_start = current_schedule.ultimate_start
            first_start = current_schedule.first_start

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=first_start,
            end=ultimate_start,
            min_kwh=self.consumption_kwh,
            peak_duration_h=self.runtime_hours,
            order='first' if current_schedule.fast else 'last'
        )).timestamp

        if planned_start >= now + self.min_start_interval:
            self.app.log.debug(f'''Rescheduled Legionella cycle. First start: {first_start},
                    planned start: {planned_start},
                    ultimate_start: {ultimate_start}''')
            current_schedule.first_start = first_start
            current_schedule.ultimate_start = ultimate_start
            current_schedule.planned_start = planned_start
            await current_schedule.save()
        else:
            self.app.log.debug(
                f'Newly planned_start of {planned_start} is too close to current time, not rescheduling.')

    async def postpone(self):
        current_schedule = await DhwSchedule.from_mode('legionella')
        if current_schedule is None:
            return

        self.app.log.debug('Postponing Legionella cycle')

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))

        if current_schedule.retry >= self.max_retry:
            self.app.log.debug('We are already at maximum number of retries.')
            raise MaxRetriesExceededError

        first_start = max(
            now + self.min_start_interval_retry,
            current_schedule.first_start
        )

        if first_start >= current_schedule.ultimate_start:
            self.app.log.debug('First start would be after ultimate start.')
            raise MaxRetriesExceededError

        planned_start = (await self.app.clients.mme_soleil.get_peak_production(
            start=first_start,
            end=current_schedule.ultimate_start,
            min_kwh=self.consumption_kwh,
            peak_duration_h=self.runtime_hours,
            order='first' if current_schedule.fast else 'last'
        )).timestamp

        self.app.log.debug(f'''Postponing (retry {current_schedule.retry + 1})
                           First start: {first_start},
                           planned start: {planned_start},
                           ultimate_start: {current_schedule.ultimate_start}''')

        current_schedule.first_start = first_start
        current_schedule.planned_start = planned_start
        current_schedule.retry = current_schedule.retry + 1
        await current_schedule.save()

    async def can_start_legionella(self):
        current_temp, can_start = await asyncio.gather(
            self.app.clients.hab.get_current_dhw_temp(),
            self.app.services.controller.can_start()
        )

        if current_temp.value > self.legionella_temp_min_start:
            # too hot to start
            self.app.log.debug(
                f'DHW temperature of {current_temp.value} °C  still too hot.')
            return False
        else:
            return can_start

    async def start(self, force_start=False):
        operating_mode = await OperatingMode.from_circuit('dhw')
        if operating_mode.mode in [DhwMode.PENDING_LEGIONELLA, DhwMode.RUNNING_LEGIONELLA]:
            return

        self.app.log.debug('Starting Legionella cycle')

        if not force_start:
            can_start = await self.can_start_legionella()
            if not can_start:
                self.app.log.debug('Cannot start Legionella cycle.')
                try:
                    await self.postpone()
                except MaxRetriesExceededError:
                    # start anyway
                    self.app.log.debug(
                        'Cannot postpone anymore, starting anyway.')
                    pass
                else:
                    return

        outside_temp = await self.app.clients.hab.get_current_outside_temp()

        if self.running_mode == DhwRunningMode.NORMAL or (
            self.running_mode == DhwRunningMode.AUTO
            and outside_temp.value > self.running_mode_stepped_max_temp
        ):
            dhw_target_setpoint = DhwSetpoint("target", self.dhw_temp_legionella)

            await asyncio.gather(
                dhw_target_setpoint.save(),
                self.app.clients.ecodan.set_dhw_target_temp(
                    dhw_target_setpoint.setpoint
                ),
            )
        else:
            dhw_temp = await self.app.clients.hab.get_current_dhw_temp()

            dhw_setpoint = DhwSetpoint(
                "current", math.ceil(dhw_temp.value + self.dhw_temp_drop_ecodan + 1)
            )

            dhw_target_setpoint = DhwSetpoint("target", self.dhw_temp_legionella)

            await asyncio.gather(
                dhw_setpoint.save(),
                dhw_target_setpoint.save(),
                self.app.clients.ecodan.set_dhw_target_temp(dhw_setpoint.setpoint),
            )

        self.app.log.debug(
            f'Setting {Circuit.DHW} to mode: {DhwMode.PENDING_LEGIONELLA}')
        operating_mode.mode = DhwMode.PENDING_LEGIONELLA
        await operating_mode.save()

        self.app.log.debug('Removing Legionella schedule.')
        schedule = await DhwSchedule.from_mode('legionella')
        await schedule.remove()

        dhw_schedule = await DhwSchedule.from_mode('dhw')
        if dhw_schedule is not None:
            self.app.log.debug(
                'Removing DHW schedule, will be hot enough after Legionella cycle.')
            await dhw_schedule.remove()

        self.timestamp_started = datetime.datetime.now(
            tz=pytz.timezone("Europe/Brussels")
        )

    async def step(self):
        if self.running_mode not in (DhwRunningMode.STEPPED, DhwRunningMode.AUTO):
            return

        operating_mode = await OperatingMode.from_circuit("dhw")
        if operating_mode.mode not in [DhwMode.RUNNING_LEGIONELLA]:
            return

        dhw_temp, dhw_setpoint, dhw_target_setpoint = await asyncio.gather(
            self.app.clients.hab.get_current_dhw_temp(),
            DhwSetpoint.from_type("current"),
            DhwSetpoint.from_type("target"),
        )

        if dhw_temp.value < dhw_setpoint.setpoint - self.buffer_interval:
            # not hot enough
            self.app.log.debug(
                f"Still heating up (now: {dhw_temp.value}) to normal temperature, not enabling stepping mode."
            )
        elif dhw_temp.value >= dhw_setpoint.setpoint - self.buffer_interval:
            if dhw_setpoint.setpoint <= dhw_target_setpoint.setpoint - 1:
                self.app.log.debug(
                    f"""Current DHW temperature of {dhw_temp.value}° is within {self.buffer_interval}° of current target.
                    Setting target to {dhw_setpoint.setpoint + 1}°."""
                )
                dhw_setpoint.setpoint += 1
                await asyncio.gather(
                    dhw_setpoint.save(),
                    self.app.clients.ecodan.set_dhw_target_temp(dhw_setpoint.setpoint),
                )
            else:
                self.app.log.debug(
                    f"""Current DHW temperature of {dhw_temp.value}° is not yet within {self.buffer_interval}° of current target.
                    Not increasing target yet."""
                )
        else:
            self.app.log.debug(
                f"""Current DHW temperature of {dhw_temp.value}° is not yet within {self.buffer_interval}° of current target.
                    Not increasing target yet."""
            )

    async def stop(self):
        operating_mode = await OperatingMode.from_circuit('dhw')
        if operating_mode.mode not in [DhwMode.PENDING_LEGIONELLA, DhwMode.RUNNING_LEGIONELLA]:
            return

        self.app.log.debug('Stopping Legionella cycle')

        await self.app.clients.ecodan.set_dhw_target_temp(self.dhw_temp_off)

        self.app.log.debug(f'Setting {Circuit.DHW} to mode: {DhwMode.OFF}')
        operating_mode.mode = DhwMode.OFF
        await operating_mode.save()

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))
        self.app.scheduler.add_job(
            self.plan, 'date', run_date=now + datetime.timedelta(minutes=60))

    async def update_from_state(self):
        operating_mode, current_state, dhw_temp = await asyncio.gather(
            OperatingMode.from_circuit('dhw'),
            self.app.clients.hab.get_current_state(),
            self.app.clients.hab.get_current_dhw_temp()
        )

        now = datetime.datetime.now(tz=pytz.timezone("Europe/Brussels"))

        if operating_mode.mode == DhwMode.PENDING_LEGIONELLA:
            if current_state.operating_mode == 'Hot water':
                self.app.log.debug(
                    f'Setting {Circuit.DHW} to mode: {DhwMode.RUNNING_LEGIONELLA}')
                operating_mode.mode = DhwMode.RUNNING_LEGIONELLA
                await operating_mode.save()
        elif operating_mode.mode == DhwMode.RUNNING_LEGIONELLA:
            if dhw_temp.value >= self.dhw_temp_legionella and current_state.operating_mode != 'Hot water':
                await self.stop()
            elif (
                current_state.operating_mode != "Hot water"
                and self.timestamp_started <= now - self.max_runtime_ecodan
            ):
                await self.stop()
            else:
                await self.step()

    def __scheduled_jobs(self):
        self.app.scheduler.add_job(
            self.plan, 'cron', hour='4,8,12,16,20', minute='0')
        self.app.scheduler.add_job(self.reschedule, 'cron', minute='56')
