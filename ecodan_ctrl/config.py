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

import os


class Config:
    QUART_AUTH_MODE = 'bearer'
    QUART_AUTH_BASIC_USERNAME = 'admin'
    QUART_AUTH_BASIC_PASSWORD = os.environ.get('API_ADMIN_PASS')

    ECODAN_API_BASE_URL = os.environ.get('ECODAN_API_BASE_URL')
    ECODAN_API_USERNAME = os.environ.get('ECODAN_API_USERNAME')
    ECODAN_API_PASSWORD = os.environ.get('ECODAN_API_PASSWORD')

    HAB_API_BASE_URL = os.environ.get('HAB_API_BASE_URL')
    HAB_API_USERNAME = os.environ.get('HAB_API_USERNAME')
    HAB_API_PASSWORD = os.environ.get('HAB_API_PASSWORD')

    MME_SOLEIL_BASE_URL = os.environ.get('MME_SOLEIL_BASE_URL')
    MME_SOLEIL_USERNAME = os.environ.get('MME_SOLEIL_USERNAME')
    MME_SOLEIL_PASSWORD = os.environ.get('MME_SOLEIL_PASSWORD')

    DHW_TEMP_OFF = float(os.environ.get('DHW_TEMP_OFF'))
    DHW_TEMP_BASE = float(os.environ.get('DHW_TEMP_BASE'))
    DHW_TEMP_BUFFER = float(os.environ.get('DHW_TEMP_BUFFER'))
    DHW_TEMP_DROP = float(os.environ.get('DHW_TEMP_DROP'))
    DHW_TEMP_DROP_ECODAN = float(os.environ.get('DHW_TEMP_DROP_ECODAN'))
    DHW_NORMAL_RUNTIME_HOURS = int(os.environ.get('DHW_NORMAL_RUNTIME_HOURS'))
    DHW_NORMAL_INTERVAL_MAX_HOURS = int(
        os.environ.get('DHW_NORMAL_INTERVAL_MAX_HOURS'))
    DHW_NORMAL_KWH = float(os.environ.get('DHW_NORMAL_KWH'))

    DHW_TEMP_LEGIONELLA = float(os.environ.get('DHW_TEMP_LEGIONELLA'))
    DHW_LEGIONELLA_INTERVAL_DAYS = int(
        os.environ.get('DHW_LEGIONELLA_INTERVAL_DAYS'))
    DHW_LEGIONELLA_MIN_INTERVAL_DAYS = int(
        os.environ.get('DHW_LEGIONELLA_MIN_INTERVAL_DAYS'))
    DHW_LEGIONELLA_RUNTIME_HOURS = int(
        os.environ.get('DHW_LEGIONELLA_RUNTIME_HOURS'))
    DHW_LEGIONELLA_KWH = float(os.environ.get('DHW_LEGIONELLA_KWH'))

    DHW_MAX_RETRY = int(os.environ.get('DHW_MAX_RETRY'))
    DHW_MIN_INTERVAL_MINUTES = int(os.environ.get('DHW_MIN_INTERVAL_MINUTES'))
    DHW_MIN_INTERVAL_RETRY_MINUTES = int(
        os.environ.get('DHW_MIN_INTERVAL_RETRY_MINUTES'))

    HEATING_TEMP_MIN = float(os.environ.get('HEATING_TEMP_MIN'))
    HEATING_TEMP_NIGHT = float(os.environ.get('HEATING_TEMP_NIGHT'))
    HEATING_TEMP_DAY = float(os.environ.get('HEATING_TEMP_DAY'))

    HEATING_FADE_MIN_TEMP_NIGHT = float(
        os.environ.get('HEATING_FADE_MIN_TEMP_NIGHT'))
    HEATING_FADE_MIN_TEMP_FORCE_OFF = float(
        os.environ.get('HEATING_FADE_MIN_TEMP_FORCE_OFF'))
    HEATING_FADE_MIN_CLEARSKY_RATIO = float(
        os.environ.get('HEATING_FADE_MIN_CLEARSKY_RATIO'))
    HEATING_FADE_MIN_NEXTDAY_TEMP = float(
        os.environ.get('HEATING_FADE_MIN_NEXTDAY_TEMP'))
    HEATING_FADE_PERIOD_HOURS = int(
        os.environ.get('HEATING_FADE_PERIOD_HOURS'))
    HEATING_FADE_DURING = os.environ.get('HEATING_FADE_DURING')
    HEATING_FADE_STEPS = int(os.environ.get('HEATING_FADE_STEPS'))

    DATABASE_PATH = os.environ.get('SQLITE_DB_PATH')
