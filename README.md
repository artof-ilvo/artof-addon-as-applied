# ARTOF task-map addon

Records **as-applied maps** on the ARTOF robot. While the Redis variable `pc.as_applied.record` is `true`
(toggled from the map tab of artof-system), it polls `implement.states` and stores the area swept by every
implement section, together with its `rate`, in

```
/var/lib/ilvo/field/<field>/as_applied/<implement>_<YYYYmmdd-HHMMSS>.gpkg   (layer "rate")
```

A new session starts each time recording is switched on or the active field (`pc.field.name`) changes. The
files of the running session are published in `pc.as_applied.files` (JSON list). The format and geometry live in
`artof_utils.as_applied`; this addon is only the long-running process around it.

GeoPackages open directly in QGIS (drag and drop); colour the `rate` column with a graduated style.

## Build and run

```bash
# with a local artof-utils checkout (needed until as_applied is released on PyPI)
docker build --build-context artof_utils=../../artof-utils -t axelwillekens/artof-taskmap-addon:dev .

docker run --rm --network=host -v /var/lib/ilvo:/var/lib/ilvo --name taskmap-addon axelwillekens/artof-taskmap-addon:dev
```

Settings (environment): `TASKMAP_POLL_PERIOD` (s, default 0.2), `TASKMAP_FLUSH_PERIOD` (s, default 1.0),
`TASKMAP_MIN_DISTANCE` (m, default 0.1), `REDIS_HOST` / `REDIS_PORT`.
