# ARTOF task-map addon

Records **as-applied sessions** on the ARTOF robot. While the Redis variable `pc.as_applied.record` is `true`, it
polls Redis and writes one session folder per recording. The addon switches recording on when the robot enters auto
mode (a navigation state in `auto_modes` of `settings.json`, or `pc.simulation.auto` in simulation) and off when it
leaves it; outside auto mode it can be toggled from the map tab of artof-system.

```
/var/lib/ilvo/field/<field>/as_applied/<YYYYmmdd-HHMMSS>/
    sections.gpkg   layer "sections": area swept by every implement section (implement, section, rate, time)
    points.gpkg     layer "points": robot.ref.state point with all Redis variables (+ time, lat, lon, ref.yaw)
```

Sections are written once they moved more than `TASKMAP_MIN_DISTANCE`. Points are equidistant: one every
`TASKMAP_POINT_DISTANCE` meters along the driven path, interpolated between polls so the spacing does not depend on the
speed or the poll rate; they are also logged every `TASKMAP_POINT_PERIOD` seconds while the robot stands still. A new session starts each time recording is switched on
or the active field (`pc.field.name`) changes. The running session id is published in `pc.as_applied.session`, and
`pc.as_applied.heartbeat` (unix time, every second) tells the web pages the addon is alive. The format and geometry
live in `artof_utils.as_applied`; this addon is only the long-running process around it.

Both GeoPackages open directly in QGIS (drag and drop); the artof-system **Applied** tab shows and filters them.

## Build and run

```bash
# with a local artof-utils checkout (needed until as_applied is released on PyPI)
docker build --build-context artof_utils=../../artof-utils -t axelwillekens/artof-addon-as-applied:dev .

docker run --rm --network=host -v /var/lib/ilvo:/var/lib/ilvo --name artof-addon-as-applied axelwillekens/artof-addon-as-applied:dev
```

Settings (environment): `TASKMAP_POLL_PERIOD` (s, default 0.2), `TASKMAP_FLUSH_PERIOD` (s, default 1.0),
`TASKMAP_MIN_DISTANCE` (m, default 0.1), `TASKMAP_POINT_DISTANCE` (m, default 1.0), `TASKMAP_POINT_PERIOD` (s, default 5.0), `REDIS_HOST` / `REDIS_PORT`.
