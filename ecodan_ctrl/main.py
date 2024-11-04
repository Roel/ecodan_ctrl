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
import logging

from quart import Quart
from quart_auth import QuartAuth

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import Config
from db.base import Database

from clients.ecodan import EcodanClient
from clients.hab import HabClient
from clients.mme_soleil import MmeSoleilClient

from services.dhw import DhwService
from services.heating import HeatingService
from services.legionella import LegionellaService
from services.controller import ControllerService

from blueprints.grafana import grafana


class Clients:
    def __init__(self, app):
        self.app = app

        self.ecodan = EcodanClient(
            app=self.app,
            base_url=self.app.config['ECODAN_API_BASE_URL'],
            username=self.app.config['ECODAN_API_USERNAME'],
            password=self.app.config['ECODAN_API_PASSWORD']
        )

        self.hab = HabClient(
            app=self.app,
            base_url=self.app.config['HAB_API_BASE_URL'],
            username=self.app.config['HAB_API_USERNAME'],
            password=self.app.config['HAB_API_PASSWORD']
        )

        self.mme_soleil = MmeSoleilClient(
            app=self.app,
            base_url=self.app.config['MME_SOLEIL_BASE_URL'],
            username=self.app.config['MME_SOLEIL_USERNAME'],
            password=self.app.config['MME_SOLEIL_PASSWORD']
        )

    async def shutdown(self):
        await asyncio.gather(
            self.hab.shutdown(),
            self.ecodan.shutdown(),
            self.mme_soleil.shutdown()
        )


class Services:
    def __init__(self, app):
        self.app = app

        self.legionella = LegionellaService(app)
        self.dhw = DhwService(app)
        self.heating = HeatingService(app)

        self.controller = ControllerService(app)


class Logger:
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger('ecodan_ctrl')
        hdlr = logging.StreamHandler()
        hdlr.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.logger.addHandler(hdlr)
        self.logger.setLevel(logging.DEBUG)

    def log(self, *args, **kwargs):
        return self.logger.log(*args, **kwargs)

    def debug(self, message):
        return self.log(logging.DEBUG, message)

    def info(self, message):
        return self.log(logging.INFO, message)

    def warning(self, message):
        return self.log(logging.WARNING, message)

    def error(self, message):
        return self.log(logging.ERROR, message)


app = Quart(__name__)
app.config.from_object(Config)
app.secret_key = app.config['SECRET_KEY']

app.db = Database(app)
app.auth = QuartAuth(app)
app.log = Logger(app)


@app.before_serving
async def startup():
    await app.db.migrate()

    loop = asyncio.get_event_loop()

    app.scheduler = AsyncIOScheduler(event_loop=loop)
    app.scheduler.start()

    app.clients = Clients(app)
    app.services = Services(app)

    await app.services.controller.set_operating_mode_from_state()
    await app.services.legionella.plan()

    await app.services.heating.update_from_state()
    await app.services.heating.plan()

    app.register_blueprint(grafana, url_prefix='/grafana')


@app.after_serving
async def shutdown():
    app.scheduler.shutdown()
    await app.clients.shutdown()
