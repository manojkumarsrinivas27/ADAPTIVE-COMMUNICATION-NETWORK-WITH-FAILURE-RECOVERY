import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adaptive_controller import AdaptiveController


class BaselineController(AdaptiveController):
    ADAPTIVE = False
