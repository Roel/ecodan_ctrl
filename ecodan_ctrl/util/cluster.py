# Ecodan controller
# Copyright (C) 2023-2026  Roel Huybrechts

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


class Cluster:
    def __init__(self, cluster_set, max_size):
        self.cluster_set = cluster_set
        self.max_size = max_size

        self.data = []

    def __chrono(self):
        return sorted(self.data, key=lambda i: i.timestamp)

    def is_empty(self):
        return len(self.data) == 0

    def get_start(self):
        if self.is_empty():
            return None

        return self.__chrono()[0].timestamp

    def get_end(self):
        if self.is_empty():
            return None

        return self.__chrono()[-1].timestamp

    def is_inside(self, timestamp):
        if self.get_start() is None or self.get_end() is None:
            return False

        return self.get_start() <= timestamp <= self.get_end()

    def add_datapoint(self, timedata):
        ts = timedata.timestamp

        if self.is_empty() and self.cluster_set.matches_interval(ts, ts, self):
            self.data.append(timedata)
            return True
        elif self.is_empty():
            return False

        if ts >= self.get_start() and ts <= self.get_end():
            self.data.append(timedata)
            return True

        if (
            ts < self.get_start()
            and self.get_end() - ts <= self.max_size
            and self.cluster_set.matches_interval(ts, self.get_end(), self)
        ):
            self.data.append(timedata)
            return True

        if (
            ts > self.get_end()
            and (ts - self.get_start()) <= self.max_size
            and self.cluster_set.matches_interval(self.get_start(), ts, self)
        ):
            self.data.append(timedata)
            return True

        return False


class ClusterSet:
    def __init__(self, max_count, max_size, min_interval):
        self.max_count = max_count
        self.max_size = max_size
        self.min_interval = min_interval

        self.clusters = []

    def add_datapoint(self, timedata):
        if len(self.clusters) == 0:
            self.clusters.append(Cluster(self, self.max_size))

        for c in self.clusters:
            added = c.add_datapoint(timedata)
            if added:
                return True

        if len(self.clusters) < self.max_count:
            cluster = Cluster(self, self.max_size)
            self.clusters.append(cluster)
            added = cluster.add_datapoint(timedata)
            if added:
                return True
            else:
                self.clusters.remove(cluster)

        return False

    def matches_interval(self, start, end, excluding_cluster):
        for c in self.clusters:
            if c == excluding_cluster:
                continue

            if c.is_inside(end + self.min_interval):
                return False

            if c.is_inside(start - self.min_interval):
                return False

        return True
