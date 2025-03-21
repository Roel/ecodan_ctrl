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

from quart import Blueprint, request, current_app as app
from quart_auth import basic_auth_required

from db.models.dhw_schedule import DhwSchedule

grafana = Blueprint('grafana', __name__)


def get_range(data):
    date_from = pytz.utc.localize(datetime.datetime.strptime(
        data['range']['from'][:-5], '%Y-%m-%dT%H:%M:%S')).astimezone(pytz.timezone('Europe/Brussels'))

    date_to = pytz.utc.localize(datetime.datetime.strptime(
        data['range']['to'][:-5], '%Y-%m-%dT%H:%M:%S')).astimezone(pytz.timezone('Europe/Brussels'))

    return date_from, date_to


def get_targets(data):
    return [i['target'] for i in data['targets']]


def format_date(timestamp):
    days = {
        0: 'Ma',
        1: 'Di',
        2: 'Woe',
        3: 'Do',
        4: 'Vr',
        5: 'Za',
        6: 'Zo'
    }

    r = ''

    if timestamp.date() > datetime.date.today():
        r += days.get(timestamp.weekday()) + ' '

    r += timestamp.strftime('%H:%M')
    return r


@grafana.get("/")
@basic_auth_required()
async def test_connection():
    return {'status': 'ok'}, 200


@grafana.post("/metrics")
@basic_auth_required()
async def get_metrics():
    return [
        {"label": "Next DHW cycle", "value": "dhw_next_cycle"}
    ]


@grafana.post("/metric-payload-options")
@basic_auth_required()
async def get_metric_payload_options():
    return []


@grafana.post("/query")
@basic_auth_required()
async def query():
    data = await request.json

    date_from, date_to = get_range(data)
    targets = get_targets(data)

    date_from = date_from - datetime.timedelta(minutes=10)
    date_to = date_to + datetime.timedelta(minutes=10)

    now = int(datetime.datetime.now().strftime('%s'))*1000

    result = []

    for t in targets:
        if t == 'dhw_next_cycle':
            next_cycle = await DhwSchedule.get_next_planned()

            modes = {
                'dhw': '♨',
                'legionella': '🌶'
            }

            if next_cycle is None:
                r = '⏸'
            else:
                r = modes.get(next_cycle.mode, '?') + ' '
                r += format_date(next_cycle.planned_start)

            datapoints = [[r, now]]

            result.append({
                'target': 'dhw_next_cycle',
                'datapoints': datapoints
            })

    return result
