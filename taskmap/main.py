"""
ARTOF task-map addon: records as-applied sessions while ``pc.as_applied.record`` is true. Recording starts when the robot
enters auto mode and stops when it leaves it; outside auto mode the flag is toggled from the map page.

Every poll it reads ``implement.states`` (swept section polygons with their rate) and ``robot.ref.state`` (robot
position, logged with all redis variables) and appends them through ``artof_utils.as_applied`` to
``<ILVO_PATH>/field/<field>/as_applied/<YYYYmmdd-HHMMSS>/{sections,points}.gpkg``.
"""
import signal
import time
from glob import glob
from os import getenv, path

import pyogrio

import artof_utils.paths as paths
from artof_utils import as_applied
from artof_utils.redis_instance import redis_server
from artof_utils.schemas.settings import load_settings

POLL_PERIOD = float(getenv('TASKMAP_POLL_PERIOD', '0.2'))     # seconds between redis reads
FLUSH_PERIOD = float(getenv('TASKMAP_FLUSH_PERIOD', '1.0'))   # seconds between writes to the GeoPackages
MIN_DISTANCE = float(getenv('TASKMAP_MIN_DISTANCE', '0.1'))   # meters moved before a section or sample is recorded
POINT_DISTANCE = float(getenv('TASKMAP_POINT_DISTANCE', '1.0'))  # meters between points along the driven path
POINT_PERIOD = float(getenv('TASKMAP_POINT_PERIOD', '5.0'))   # seconds between points while standing still

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


def point_attributes(ref_state: dict) -> dict:
    """All redis variables (as on the monitor page) plus the heading of the reference point. The recorder adds the
    WGS84 position, since points are interpolated between polls to keep them equidistant."""
    rotation = ref_state.get('R') or [None, None, None]
    return {'ref.yaw': rotation[2], **redis_server.get_all_values()}


# Published when no session is recording. Not '': the Redis client of artof-core (redis-cpp) leaves the CRLF of an
# empty bulk string in its stream, so every artof-core process that reads the key fails on the next reply.
NO_SESSION = '-'


def publish_session(recorder):
    redis_server.set_value(as_applied.REDIS_SESSION, recorder.session if recorder and recorder.layers else NO_SESSION)


def close(recorder):
    if recorder is None:
        return
    recorder.flush()
    print('Stopped recording %s: session %s, layers %s' % (recorder.field_name, recorder.session,
                                                           ', '.join(recorder.layers) or 'none'))


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    recorder = None
    auto_mode = as_applied.AutoModeRecording(redis_server)
    last_flush = last_beat = time.monotonic()
    as_applied.beat(redis_server)
    publish_session(None)
    print('Task-map addon started (poll %.2fs, flush %.1fs, auto modes: %s)'
          % (POLL_PERIOD, FLUSH_PERIOD, ', '.join(auto_mode.names)))

    while running:
        if time.monotonic() - last_beat >= 1.0:
            as_applied.beat(redis_server)
            last_beat = time.monotonic()

        auto_mode.update()
        recording = as_applied.is_recording(redis_server)
        field_name = current_field_name() if recording else None

        # Close the session when recording stops or the robot switches field
        if recorder is not None and (not recording or field_name != recorder.field_name):
            close(recorder)
            recorder = None
            publish_session(None)

        if recording and field_name:
            if recorder is None:
                recorder = as_applied.AsAppliedRecorder(field_name, field_crs(field_name), MIN_DISTANCE, POINT_PERIOD,
                                                         point_distance=POINT_DISTANCE)
                print('Recording as-applied session %s of field %s' % (recorder.session, field_name))

            data = redis_server.get_n_json_value(['implement.states', 'robot.ref.state'])
            recorder.update(data['implement.states'])
            ref_state = data['robot.ref.state'] or {}
            xy = ref_state.get('point', {}).get('xy')
            # All variables are only read when the point is logged
            recorder.log_point(xy, lambda: point_attributes(ref_state))

            if time.monotonic() - last_flush >= FLUSH_PERIOD:
                if recorder.flush():
                    publish_session(recorder)
                last_flush = time.monotonic()

        time.sleep(POLL_PERIOD)

    close(recorder)
    publish_session(None)


if __name__ == '__main__':
    main()
