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

import pytz

from db.models.dhw_schedule import DhwSchedule
from db.models.operating_mode import Circuit, DhwMode, OperatingMode


class ControllerService:
    def __init__(self, app):
        self.app = app

        self.dhw_temp_off = self.app.config['DHW_TEMP_OFF']
        self.dhw_temp_base = self.app.config['DHW_TEMP_BASE']
        self.dhw_temp_buffer = self.app.config['DHW_TEMP_BUFFER']
        self.dhw_temp_legionella = self.app.config['DHW_TEMP_LEGIONELLA']

        self.__scheduled_jobs()

    async def set_operating_mode_from_state(self):
        current_state, setpoint, current_operating_mode = await asyncio.gather(
            self.app.clients.hab.get_current_state(),
            self.app.clients.hab.get_setpoint(),
            OperatingMode.from_circuit('dhw')
        )

        is_running_dhw = current_state.operating_mode == 'Hot water'

        self.app.log.debug('Setting operating mode from heatpump state')

        if setpoint.dhw == self.dhw_temp_off:
            mode = DhwMode.OFF
        elif setpoint.dhw < self.dhw_temp_base:
            # should be off
            await self.app.services.dhw.stop()
            return
        elif setpoint.dhw == self.dhw_temp_base:
            mode = DhwMode.RUNNING_NORMAL if is_running_dhw else DhwMode.PENDING_NORMAL
        elif self.dhw_temp_buffer >= setpoint.dhw > self.dhw_temp_base:
            mode = DhwMode.RUNNING_BUFFER
        elif setpoint.dhw == self.dhw_temp_legionella:
            mode = DhwMode.RUNNING_LEGIONELLA if is_running_dhw else DhwMode.PENDING_LEGIONELLA

        if current_operating_mode is not None and current_operating_mode.mode == mode:
            self.app.log.debug(
                f'Operating mode was already set correctly to: {mode}')
            return

        self.app.log.debug(f'Setting {Circuit.DHW} to mode: {mode}')

        operating_mode = OperatingMode(
            circuit=Circuit.DHW,
            mode=mode
        )
        await operating_mode.save()

    async def can_start(self):
        baseline_consumption, current_consumption = await asyncio.gather(
            self.app.clients.hab.get_baseline_consumption(),
            self.app.clients.hab.get_current_consumption(),
        )

        threshold = baseline_consumption.q50 + \
            (1.5 * baseline_consumption.stddev)
        can_start = current_consumption.value <= threshold

        if can_start:
            self.app.log.debug(
                f'Allowed to start cycle: current consumption of {current_consumption.value} is '
                f'below threshold value of {threshold}.')
        else:
            self.app.log.debug(
                f'Preventing start of cycle: current consumption of {current_consumption.value} is '
                f'above threshold value of {threshold}.')

        return can_start

    async def evaluate(self):

        def time_to_start(planned_start, now):
            if planned_start <= now:
                return (now - planned_start).total_seconds() <= 35
            else:
                return False

        now = datetime.datetime.now(tz=pytz.timezone('Europe/Brussels'))
        dhw_planned = await DhwSchedule.get_next_planned()

        operating_mode = await OperatingMode.from_circuit('dhw')
        om_legionella = [DhwMode.PENDING_LEGIONELLA,
                         DhwMode.RUNNING_LEGIONELLA]
        om_pending = [DhwMode.PENDING_NORMAL, DhwMode.PENDING_LEGIONELLA]

        if operating_mode.mode in om_pending and operating_mode.last_modified <= (now - datetime.timedelta(minutes=15)):
            # pending for too long, turn back off
            self.app.log.debug(
                f'DHW mode was {operating_mode.mode} for too long, aborting.')
            if operating_mode.mode == DhwMode.PENDING_NORMAL:
                await self.app.services.dhw.stop()
            elif operating_mode.mode == DhwMode.PENDING_LEGIONELLA:
                await self.app.services.legionella.stop()

        if dhw_planned is not None and dhw_planned.mode == 'legionella' and operating_mode.mode not in om_legionella:
            if time_to_start(dhw_planned.planned_start, now):
                # start
                await self.app.services.legionella.start()
            elif dhw_planned.ultimate_start < now:
                # we are already past ultimate start, replan
                await self.app.services.legionella.plan()
            elif dhw_planned.planned_start < now:
                # we are already past planned start, reschedule
                await self.app.services.legionella.reschedule()
        elif dhw_planned is not None and dhw_planned.mode == 'dhw' and operating_mode.mode == DhwMode.OFF:
            if time_to_start(dhw_planned.planned_start, now):
                # start
                await self.app.services.dhw.start()
            elif dhw_planned.ultimate_start < now:
                # we are already past ultimate start, replan
                await self.app.services.dhw.plan()
            elif dhw_planned.planned_start < now:
                # we are already past planned start, reschedule
                await self.app.services.dhw.reschedule()

        await self.app.services.legionella.update_from_state()
        await self.app.services.dhw.update_from_state()

        await self.app.services.dhw.plan()
        await self.app.services.heating.evaluate()

    def __scheduled_jobs(self):
        self.app.scheduler.add_job(self.evaluate, 'cron', second='15,45')
        self.app.scheduler.add_job(
            self.set_operating_mode_from_state, 'cron', minute='*/20')
