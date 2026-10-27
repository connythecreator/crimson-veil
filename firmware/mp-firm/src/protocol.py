"""Line-delimited JSON protocol over USB serial that impliments backend json proto

"""

import json


def _default_sink(line):
    print(line)


sink = _default_sink


def emit(message):
    sink(json.dumps(message))


def send_hello(firmware, n_electrodes, electrodes, sweep_hz):
    emit(
        {
            "type": "hello",
            "firmware": firmware,
            "n_electrodes": n_electrodes,
            "electrodes": list(electrodes),
            "sweep_hz": sweep_hz,
        }
    )


def send_frame(points):
    out = []
    for point in points:
        if isinstance(point, dict):
            entry = {"f": point["f"], "re": point["re"], "im": point["im"]}
            if "n" in point:
                entry["n"] = point["n"]
            out.append(entry)
        else:
            f, re, im = point
            out.append({"f": f, "re": re, "im": im})
    emit({"type": "frame", "points": out})


def send_telemetry(temp_esp32_c=None, temp_ad5933_c=None):
    # Battery state is owned by the Witty Pi BMS on the host, not the ESP32;
    # telemetry carries only the on-chip temperatures here.
    emit(
        {
            "type": "telemetry",
            "temp_esp32_c": temp_esp32_c,
            "temp_ad5933_c": temp_ad5933_c,
        }
    )


def send_selftest_result(
    ad5933,
    mux,
    temp_ad5933_c=None,
    firmware=None,
    error=None,
    calibration=None,
    calibration_entries=None,
    calibration_error=None,
):
    emit(
        {
            "type": "selftest_result",
            "firmware": firmware,
            "ad5933": bool(ad5933),
            "mux": bool(mux),
            "temp_ad5933_c": temp_ad5933_c,
            "calibration": calibration,
            "calibration_entries": calibration_entries,
            "calibration_error": calibration_error,
            "error": error,
        }
    )


def send_error(message):
    emit({"type": "error", "message": str(message)})


def read_line(stream):
    raw = stream.readline()
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    return raw.rstrip("\r\n")


def decode(line):
    message = json.loads(line)
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError("protocol message must be a JSON object with a 'type'")
    return message
