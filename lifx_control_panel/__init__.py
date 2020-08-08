import os
import sys

RED = [0, 65535, 65535, 3500]  # Fixes RED from appearing BLACK
HEARTBEAT_RATE_MS = 3000  # 3 seconds
FRAME_PERIOD_MS = 1500  # 1.5 seconds
LOGFILE = "lifx-control-panel.log"
APPLICATION_PATH = os.path.dirname(sys.executable)
