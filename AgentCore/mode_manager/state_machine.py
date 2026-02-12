from enum import Enum

class ModeState(Enum):
    INIT = "INIT"
    RUNNING = "RUNNING"
    WAITING_CONFIRM = "WAITING_CONFIRM"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
