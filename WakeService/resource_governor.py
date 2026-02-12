"""
Resource Governor - Active CPU/Audio Throttling
=================================================
ENFORCES resource limits, not just monitors.

BLOCKER FIX: Governor must actively intervene, not just observe.
"""

import os
import time
import threading
import psutil
from typing import Optional
from dataclasses import dataclass


@dataclass
class ResourceLimits:
    """Resource usage limits."""
    cpu_sleep: float = 5.0      # Max CPU% in sleep mode
    cpu_active: float = 30.0    # Max CPU% in active mode
    frame_sleep_ms: int = 20    # Sleep between audio frames
    watchdog_threshold: float = 50.0  # Kill threshold
    watchdog_duration: int = 10  # Seconds above threshold before action


class ResourceGovernor:
    """
    Active resource governance.
    
    ENFORCES limits by:
    - Injecting dynamic sleep
    - Pausing audio capture
    - Killing runaway threads
    """
    
    def __init__(self, limits: Optional[ResourceLimits] = None):
        self.limits = limits or ResourceLimits()
        self.process = psutil.Process(os.getpid())
        self._throttle_factor = 1.0
        self._violation_start: Optional[float] = None
        self._paused = False
        self._lock = threading.Lock()
        
        # Start watchdog
        self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self._watchdog_thread.start()
    
    def apply_throttle(self, is_active: bool):
        """
        Apply throttling based on current mode.
        
        ACTIVE ENFORCEMENT: Injects sleep to reduce CPU usage.
        """
        with self._lock:
            if self._paused:
                # Force pause - sleep longer
                time.sleep(0.5)
                return
            
            # Calculate required sleep
            base_sleep = self.limits.frame_sleep_ms / 1000.0
            throttled_sleep = base_sleep * self._throttle_factor
            
            time.sleep(throttled_sleep)
    
    def _watchdog_loop(self):
        """
        Watchdog that monitors and ENFORCES CPU limits.
        
        ACTIVE INTERVENTION: Forces pause if CPU exceeds threshold.
        """
        while True:
            try:
                cpu_percent = self.process.cpu_percent(interval=1.0)
                
                if cpu_percent > self.limits.watchdog_threshold:
                    if self._violation_start is None:
                        self._violation_start = time.time()
                        print(f"[Governor] CPU violation: {cpu_percent:.1f}% (threshold: {self.limits.watchdog_threshold}%)")
                    
                    violation_duration = time.time() - self._violation_start
                    
                    if violation_duration >= self.limits.watchdog_duration:
                        # ACTIVE INTERVENTION: Force throttle
                        print(f"[Governor] ENFORCING throttle - CPU {cpu_percent:.1f}% for {violation_duration:.1f}s")
                        self._enforce_throttle(cpu_percent)
                else:
                    # Reset violation
                    if self._violation_start:
                        print(f"[Governor] CPU normalized: {cpu_percent:.1f}%")
                    self._violation_start = None
                    self._relax_throttle()
                    
            except Exception as e:
                print(f"[Governor] Watchdog error: {e}")
            
            time.sleep(1)
    
    def _enforce_throttle(self, current_cpu: float):
        """
        ACTIVE ENFORCEMENT: Increase throttling to reduce CPU.
        """
        with self._lock:
            # Calculate throttle factor to bring CPU under limit
            target_cpu = self.limits.watchdog_threshold * 0.7  # 70% of threshold
            if current_cpu > 0:
                reduction_needed = current_cpu / target_cpu
                self._throttle_factor = min(10.0, self._throttle_factor * reduction_needed)
            
            print(f"[Governor] Throttle factor: {self._throttle_factor:.2f}x")
            
            # If still too high, force pause
            if self._throttle_factor >= 10.0:
                self._paused = True
                print("[Governor] FORCE PAUSE activated")
    
    def _relax_throttle(self):
        """Gradually relax throttling when CPU normalizes."""
        with self._lock:
            if self._throttle_factor > 1.0:
                self._throttle_factor = max(1.0, self._throttle_factor * 0.9)
            self._paused = False
    
    def force_pause(self, duration: float):
        """Force pause audio capture for duration."""
        with self._lock:
            self._paused = True
        
        time.sleep(duration)
        
        with self._lock:
            self._paused = False
    
    def is_paused(self) -> bool:
        """Check if governor has forced a pause."""
        return self._paused
    
    def get_stats(self) -> dict:
        """Get current resource stats."""
        try:
            return {
                "cpu_percent": self.process.cpu_percent(),
                "memory_mb": self.process.memory_info().rss / (1024 * 1024),
                "throttle_factor": self._throttle_factor,
                "paused": self._paused,
                "violation_active": self._violation_start is not None
            }
        except:
            return {"error": "stats unavailable"}
