"""
ARTOF task-map addon: records as-applied maps while ``pc.as_applied.record`` is true.

Polls the redis variable ``implement.states`` and appends the swept section polygons (with their rate) to
``<ILVO_PATH>/field/<field>/as_applied/<implement>_<start>.gpkg`` through ``artof_utils.as_applied``.
"""
import json
import signal
import time
from glob import glob
from os import getenv, path

import pyogrio

import artof_utils.paths as paths
from artof_utils import as_applied
from artof_utils.redis_instance import redis_server
from artof_utils.schemas.settings import load_settings

POLL_PERIOD = float(getenv('TASKMAP_POLL_PERIOD', '0.2'))     # seconds between implement.states reads
FLUSH_PERIOD = float(getenv('TASKMAP_FLUSH_PERIOD', '1.0'))   # seconds between writes to the GeoPackage
MIN_DISTANCE = float(getenv('TASKMAP_MIN_DISTANCE', '0.1'))   # meters a section moves before it is recorded

running = True


def stop(*_):
    global running
    running = False


def current_field_name() -> str:
    return redis_server.get_value('pc.field.name')


def field_crs(field_name: str):
    """CRS of the field's geofence, or the robot's UTM zone when the field has none."""
    shapefiles = glob(path.join(paths.fields, field_name, 'geofence', '*.shp'))
    if shapefiles:
        crs = pyogrio.read_info(shapefiles[0]).get('crs')
        if crs:
            return crs
    return 'EPSG:326%d' % load_settings().gps.utm_zone


def publish_files(recorder):
    redis_server.set_value(as_applied.REDIS_FILES, json.dumps(recorder.files if recorder else []))


def close(recorder):
    if recorder is None:
        return
    recorder.flush()
    print('Stopped recording %s: %s' % (recorder.field_name, ', '.join(recorder.files) or 'nothing written'))


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    recorder = None
    last_flush = time.monotonic()
    publish_files(None)
    print('Task-map addon started (poll %.2fs, flush %.1fs)' % (POLL_PERIOD, FLUSH_PERIOD))

    while running:
        recording = as_applied.is_recording(redis_server)
        field_name = current_field_name() if recording else None

        # Close the session when recording stops or the robot switches field
        if recorder is not None and (not recording or field_name != recorder.field_name):
            close(recorder)
            recorder = None

        if recording and field_name:
            if recorder is None:
                recorder = as_applied.AsAppliedRecorder(field_name, field_crs(field_name), MIN_DISTANCE)
                print('Recording as-applied map of field %s' % field_name)

            recorder.update(redis_server.get_json_value('implement.states'))

            if time.monotonic() - last_flush >= FLUSH_PERIOD:
                if recorder.flush():
                    publish_files(recorder)
                last_flush = time.monotonic()

        time.sleep(POLL_PERIOD)

    close(recorder)
    publish_files(None)


if __name__ == '__main__':
    main()
