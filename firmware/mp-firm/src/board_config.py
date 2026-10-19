"""On-device configuration written by the firmware uploader.

`hardware/firmware_upload.py` overwrites this file on the ESP32 with the chosen
mode. Keeping it a plain module means the firmware can read it with a normal
import on MicroPython.
"""

USE_MOCK = False
