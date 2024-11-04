# Ecodan controller

This program is a Python program that allows controlling an Ecodan air/water heatpump to optimize its efficiency.

It provides:
- planning legionella cycle
- planning normal DHW cycle
- day/night heating schedule
- Grafana API

It connects to:
- [ecodan](https://github.com/Roel/ecodan) to control DHW and heating setpoints
- HAB API to get necessary statistics about heatpump and power meter
- Madame Soleil to get prediction of solar production