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


def read_secret(variable_name):
    if f'{variable_name}_FILE' in os.environ:
        with open(os.environ.get(f'{variable_name}_FILE'), 'r') as secret_file:
            secret = secret_file.read()
    else:
        secret = os.environ.get(variable_name, None)
    return secret


class Config:
    QUART_AUTH_MODE = 'bearer'
    QUART_AUTH_BASIC_USERNAME = 'admin'
    QUART_AUTH_BASIC_PASSWORD = read_secret('API_ADMIN_PASS')

    ECODAN_API_BASE_URL = os.environ.get('ECODAN_API_BASE_URL')
    ECODAN_API_USERNAME = os.environ.get('ECODAN_API_USERNAME')
    ECODAN_API_PASSWORD = read_secret('ECODAN_API_PASSWORD')

    HAB_API_BASE_URL = os.environ.get('HAB_API_BASE_URL')
    HAB_API_USERNAME = os.environ.get('HAB_API_USERNAME')
    HAB_API_PASSWORD = read_secret('HAB_API_PASSWORD')

    MME_SOLEIL_BASE_URL = os.environ.get('MME_SOLEIL_BASE_URL')
    MME_SOLEIL_USERNAME = os.environ.get('MME_SOLEIL_USERNAME')
    MME_SOLEIL_PASSWORD = read_secret('MME_SOLEIL_PASSWORD')

    DHW_RUNNING_MODE = os.environ.get('DHW_RUNNING_MODE')
    DHW_RUNNING_MODE_AUTO_STEP_MAX_TEMP = float(
        os.environ.get("DHW_RUNNING_MODE_AUTO_STEP_MAX_TEMP")
    )

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

    DHW_ECODAN_MAX_RUNTIME_HOURS = int(os.environ.get("DHW_ECODAN_MAX_RUNTIME_HOURS"))

    DHW_MAX_RETRY = int(os.environ.get('DHW_MAX_RETRY'))
    DHW_MIN_INTERVAL_MINUTES = int(os.environ.get('DHW_MIN_INTERVAL_MINUTES'))
    DHW_MIN_INTERVAL_RETRY_MINUTES = int(
        os.environ.get('DHW_MIN_INTERVAL_RETRY_MINUTES'))

    HEATING_TEMP_MIN = float(os.environ.get('HEATING_TEMP_MIN'))
    HEATING_TEMP_NIGHT = float(os.environ.get('HEATING_TEMP_NIGHT'))
    HEATING_TEMP_DAY = float(os.environ.get('HEATING_TEMP_DAY'))

    HEATING_BUFFER_MIN_CLEARSKY_RATIO = float(
        os.environ.get('HEATING_BUFFER_MIN_CLEARSKY_RATIO'))
    HEATING_BUFFER_MIN_PRODUCTION_W = float(
        os.environ.get('HEATING_BUFFER_MIN_PRODUCTION_W'))
    HEATING_BUFFER_MIN_PRODUCTION_HOURS = float(
        os.environ.get('HEATING_BUFFER_MIN_PRODUCTION_HOURS'))
    HEATING_BUFFER_MIN_PREDICTION_RATIO = float(
        os.environ.get('HEATING_BUFFER_MIN_PREDICTION_RATIO'))
    HEATING_BUFFER_TEMP_ADDED = float(
        os.environ.get('HEATING_BUFFER_TEMP_ADDED'))
    HEATING_BUFFER_MAX_TEMP_NIGHT = float(
        os.environ.get('HEATING_BUFFER_MAX_TEMP_NIGHT'))

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

    HEATING_SUMMER_MODE_MIN_OUTSIDE = float(
        os.environ.get('HEATING_SUMMER_MODE_MIN_OUTSIDE'))
    HEATING_SUMMER_MODE_MIN_OUTSIDE_DAYS = int(
        os.environ.get('HEATING_SUMMER_MODE_MIN_OUTSIDE_DAYS'))
    HEATING_SUMMER_MODE_MIN_INSIDE = float(
        os.environ.get('HEATING_SUMMER_MODE_MIN_INSIDE'))
    HEATING_SUMMER_MODE_MIN_INSIDE_FORCE = float(
        os.environ.get('HEATING_SUMMER_MODE_MIN_INSIDE_FORCE'))
    HEATING_SUMMER_MODE_MAX_OUTSIDE_FORCE_OFF = float(
        os.environ.get('HEATING_SUMMER_MODE_MAX_OUTSIDE_FORCE_OFF'))
    HEATING_SUMMER_MODE_TEMP = float(os.environ.get('HEATING_SUMMER_MODE_TEMP'))

    DATABASE_PATH = os.environ.get('SQLITE_DB_PATH')
