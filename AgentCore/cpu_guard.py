"""
CPU Guard - Performance Governor
==================================
Monitors and throttles for Intel UHD safety.

Sprint 6: Conversational Intelligence
"""

import os
import time
import psutil
from typing import Callable, Optional
from threading import Thread, Event
from dataclasses import dataclass


@dataclass
class SystemMetrics:
    """Current system metrics."""
    cpu_percent: float
    memory_percent: float
    available_memory_mb: float
    is_safe: bool
    throttle_reason: Optional[str] = None


class CPUGuard:
    """
    Performance governor for Intel UHD systems.
    
    Ensures:
    - CPU stays under safe thresholds
    - LLM pauses if system stressed
    - Wake detection always prioritized
    """
    
    # Thresholds (conservative for shared memory GPU)
    CPU_WARN = 70       # Warn at 70%
    CPU_CRITICAL = 85   # Throttle at 85%
    MEM_WARN = 75       # Warn at 75%
    MEM_CRITICAL = 85   # Throttle at 85%
    
    # Sampling
    SAMPLE_INTERVAL = 2.0  # seconds
    
    def __init__(self):
        self._running = Event()
        self._throttled = Event()
        self._monitor_thread: Optional[Thread] = None
        self._callbacks: list = []
        self._last_metrics: Optional[SystemMetrics] = None
    
    def start(self):
        """Start monitoring."""
        if self._running.is_set():
            return
        
        self._running.set()
        self._monitor_thread = Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        print("[CPUGuard] Started monitoring")
    
    def stop(self):
        """Stop monitoring."""
        self._running.clear()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        print("[CPUGuard] Stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running.is_set():
            metrics = self.get_metrics()
            self._last_metrics = metrics
            
            # Check thresholds
            if not metrics.is_safe:
                if not self._throttled.is_set():
                    self._throttled.set()
                    self._notify_throttle(True, metrics.throttle_reason)
            else:
                if self._throttled.is_set():
                    self._throttled.clear()
                    self._notify_throttle(False)
            
            time.sleep(self.SAMPLE_INTERVAL)
    
    def get_metrics(self) -> SystemMetrics:
        """Get current system metrics."""
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        
        is_safe = True
        reason = None
        
        if cpu >= self.CPU_CRITICAL:
            is_safe = False
            reason = f"CPU at {cpu:.0f}%"
        elif mem.percent >= self.MEM_CRITICAL:
            is_safe = False
            reason = f"Memory at {mem.percent:.0f}%"
        
        return SystemMetrics(
            cpu_percent=cpu,
            memory_percent=mem.percent,
            available_memory_mb=mem.available / (1024 * 1024),
            is_safe=is_safe,
            throttle_reason=reason
        )
    
    def is_throttled(self) -> bool:
        """Check if currently throttled."""
        return self._throttled.is_set()
    
    def should_proceed(self, task_type: str = "default") -> bool:
        """
        Check if a task should proceed.
        
        Args:
            task_type: Type of task ("llm", "action", "wake")
            
        Returns:
            True if task can proceed
        """
        # Always allow wake detection
        if task_type == "wake":
            return True
        
        # Block LLM if throttled
        if task_type == "llm" and self._throttled.is_set():
            return False
        
        # Check current state
        metrics = self.get_metrics()
        return metrics.is_safe
    
    def wait_for_capacity(self, timeout: float = 30) -> bool:
        """
        Wait until system has capacity.
        
        Args:
            timeout: Max wait time
            
        Returns:
            True if capacity available, False if timeout
        """
        start = time.time()
        
        while time.time() - start < timeout:
            if self.should_proceed():
                return True
            time.sleep(1)
        
        return False
    
    def register_callback(self, callback: Callable[[bool, Optional[str]], None]):
        """
        Register throttle callback.
        
        Args:
            callback: Function(throttled: bool, reason: Optional[str])
        """
        self._callbacks.append(callback)
    
    def _notify_throttle(self, throttled: bool, reason: str = None):
        """Notify callbacks of throttle state change."""
        for callback in self._callbacks:
            try:
                callback(throttled, reason)
            except:
                pass
        
        if throttled:
            print(f"[CPUGuard] THROTTLED: {reason}")
        else:
            print("[CPUGuard] Throttle released")
    
    def get_status(self) -> dict:
        """Get current status."""
        metrics = self._last_metrics or self.get_metrics()
        
        return {
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "available_memory_mb": int(metrics.available_memory_mb),
            "is_safe": metrics.is_safe,
            "is_throttled": self._throttled.is_set(),
            "throttle_reason": metrics.throttle_reason
        }
    
    # Context manager
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, *args):
        self.stop()


# Singleton instance
_guard: Optional[CPUGuard] = None

def get_cpu_guard() -> CPUGuard:
    """Get singleton CPUGuard instance."""
    global _guard
    if _guard is None:
        _guard = CPUGuard()
    return _guard


def test_cpu_guard():
    """Test CPU guard."""
    print("CPU Guard Test")
    print("=" * 50)
    
    guard = CPUGuard()
    
    # Get metrics
    metrics = guard.get_metrics()
    print(f"CPU: {metrics.cpu_percent:.1f}%")
    print(f"Memory: {metrics.memory_percent:.1f}%")
    print(f"Available: {metrics.available_memory_mb:.0f} MB")
    print(f"Safe: {metrics.is_safe}")
    
    # Check proceed
    print(f"\nShould proceed (default): {guard.should_proceed()}")
    print(f"Should proceed (wake): {guard.should_proceed('wake')}")
    print(f"Should proceed (llm): {guard.should_proceed('llm')}")
    
    # Status
    print(f"\nStatus: {guard.get_status()}")


if __name__ == "__main__":
    test_cpu_guard()
