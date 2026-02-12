"""
Health Monitor - Crash Detection and Recovery
===============================================
Monitors service health with heartbeats and triggers recovery.
"""

import os
import sys
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable


# Configure logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class HealthMonitor:
    """
    Monitors JARVIS service health.
    
    Features:
    - Periodic heartbeats
    - Missed heartbeat detection
    - Crash logging
    - Recovery triggering
    """
    
    HEARTBEAT_INTERVAL = 5.0  # seconds
    MAX_MISSED_HEARTBEATS = 3
    
    def __init__(self, on_failure: Optional[Callable] = None):
        self.on_failure = on_failure
        self._running = False
        self._last_heartbeat = time.time()
        self._missed_count = 0
        self._thread: Optional[threading.Thread] = None
        self._logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup rotating log file."""
        logger = logging.getLogger("JARVISHealth")
        logger.setLevel(logging.INFO)
        
        # File handler
        log_file = LOG_DIR / f"jarvis_health_{datetime.now().strftime('%Y%m%d')}.log"
        handler = logging.FileHandler(log_file)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        logger.addHandler(handler)
        
        return logger
    
    def start(self):
        """Start health monitoring."""
        self._running = True
        self._last_heartbeat = time.time()
        self._missed_count = 0
        
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        
        self._logger.info("Health monitor started")
    
    def stop(self):
        """Stop health monitoring."""
        self._running = False
        self._logger.info("Health monitor stopped")
    
    def heartbeat(self):
        """Record a heartbeat."""
        self._last_heartbeat = time.time()
        self._missed_count = 0
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            time.sleep(self.HEARTBEAT_INTERVAL)
            
            # Check for missed heartbeats
            elapsed = time.time() - self._last_heartbeat
            
            if elapsed > self.HEARTBEAT_INTERVAL * 1.5:
                self._missed_count += 1
                self._logger.warning(f"Missed heartbeat #{self._missed_count}")
                
                if self._missed_count >= self.MAX_MISSED_HEARTBEATS:
                    self._handle_failure("Too many missed heartbeats")
    
    def _handle_failure(self, reason: str):
        """Handle detected failure."""
        self._logger.error(f"FAILURE DETECTED: {reason}")
        
        # Log to Windows Event Log if available
        try:
            import win32evtlog
            import win32evtlogutil
            win32evtlogutil.ReportEvent(
                "JARVIS",
                1,  # Event ID
                eventCategory=0,
                eventType=win32evtlog.EVENTLOG_ERROR_TYPE,
                strings=[f"JARVIS failure: {reason}"],
                data=None
            )
        except:
            pass
        
        # Trigger recovery callback
        if self.on_failure:
            self.on_failure(reason)
    
    def log_crash(self, error: Exception):
        """Log a crash event."""
        self._logger.error(f"CRASH: {type(error).__name__}: {error}")
        
        # Write crash dump
        crash_file = LOG_DIR / f"crash_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(crash_file, "w") as f:
            import traceback
            f.write(f"Time: {datetime.now()}\n")
            f.write(f"Error: {error}\n")
            f.write(f"Traceback:\n{traceback.format_exc()}")
        
        self._logger.info(f"Crash dump written to {crash_file}")
    
    def get_status(self) -> dict:
        """Get current health status."""
        return {
            "running": self._running,
            "last_heartbeat": self._last_heartbeat,
            "missed_count": self._missed_count,
            "healthy": self._missed_count < self.MAX_MISSED_HEARTBEATS
        }
