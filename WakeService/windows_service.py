"""
Windows Service - True OS-Level JARVIS Service
================================================
Runs under LocalService with split architecture for mic access.

Architecture:
- Windows Service = Supervisor (runs before login)
- User-session helper = Audio capture (IPC via named pipe)
"""

import os
import sys
import time
import socket
import threading
import subprocess
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import win32serviceutil
    import win32service
    import win32event
    import servicemanager
    import win32pipe
    import win32file
    PYWIN32_AVAILABLE = True
except ImportError:
    PYWIN32_AVAILABLE = False
    print("pywin32 not available - service mode disabled")


# Named pipe for IPC between service and user-session helper
PIPE_NAME = r'\\.\pipe\JARVISAudioPipe'


class JarvisWindowsService(win32serviceutil.ServiceFramework):
    """
    True Windows Service running under LocalService.
    
    BLOCKER FIX: Uses split architecture:
    - This service = supervisor, no direct mic access
    - User helper = audio capture, communicates via named pipe
    """
    
    _svc_name_ = "JARVISService"
    _svc_display_name_ = "JARVIS Voice Assistant"
    _svc_description_ = "Always-on voice assistant service (runs before login)"
    
    def __init__(self, args):
        if PYWIN32_AVAILABLE:
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False
        self.helper_process = None
        self.health_thread = None
        self.pipe_handle = None
        
    def SvcStop(self):
        """
        MANDATORY: Graceful shutdown handler.
        Called by Windows Service Manager.
        """
        self.log("Service stop requested")
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        
        # Signal stop
        self.running = False
        win32event.SetEvent(self.stop_event)
        
        # Stop helper process
        self._stop_helper()
        
        # Close pipe
        if self.pipe_handle:
            try:
                win32file.CloseHandle(self.pipe_handle)
            except:
                pass
        
        self.log("Service stopped")
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
    
    def SvcDoRun(self):
        """
        MANDATORY: Main service entry point.
        Called by Windows Service Manager on start.
        """
        self.log("Service starting...")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        
        self.running = True
        
        # Start health monitor
        self.health_thread = threading.Thread(target=self._health_loop, daemon=True)
        self.health_thread.start()
        
        # Create named pipe for IPC
        self._create_pipe()
        
        # Start user-session helper
        self._start_helper()
        
        # Main service loop
        self._main_loop()
    
    def _main_loop(self):
        """Main service loop - supervises helper and handles IPC."""
        self.log("Entering main loop")
        
        while self.running:
            # Wait for stop event or timeout
            result = win32event.WaitForSingleObject(self.stop_event, 5000)
            
            if result == win32event.WAIT_OBJECT_0:
                # Stop event signaled
                break
            
            # Check helper health
            if self.helper_process and self.helper_process.poll() is not None:
                self.log("Helper process died, restarting...")
                self._start_helper()
            
            # Read from pipe if data available
            self._check_pipe()
    
    def _create_pipe(self):
        """Create named pipe for IPC with user helper."""
        try:
            self.pipe_handle = win32pipe.CreateNamedPipe(
                PIPE_NAME,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_READMODE_MESSAGE | win32pipe.PIPE_WAIT,
                1,  # Max instances
                65536,  # Out buffer
                65536,  # In buffer
                0,  # Default timeout
                None  # Security
            )
            self.log("Named pipe created")
        except Exception as e:
            self.log(f"Pipe creation failed: {e}")
    
    def _start_helper(self):
        """Start user-session audio helper."""
        helper_script = PROJECT_ROOT / "WakeService" / "audio_helper.py"
        
        if not helper_script.exists():
            self.log(f"Helper script not found: {helper_script}")
            return
        
        try:
            # Start helper in user session
            python_path = sys.executable
            self.helper_process = subprocess.Popen(
                [python_path, str(helper_script)],
                cwd=str(PROJECT_ROOT),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            self.log(f"Helper started, PID: {self.helper_process.pid}")
        except Exception as e:
            self.log(f"Failed to start helper: {e}")
    
    def _stop_helper(self):
        """Stop user-session helper."""
        if self.helper_process:
            try:
                self.helper_process.terminate()
                self.helper_process.wait(timeout=5)
            except:
                self.helper_process.kill()
            self.helper_process = None
            self.log("Helper stopped")
    
    def _check_pipe(self):
        """Check for messages from helper."""
        if not self.pipe_handle:
            return
        
        try:
            # Non-blocking read attempt
            result, data = win32file.ReadFile(self.pipe_handle, 4096)
            if data:
                message = data.decode('utf-8').strip()
                self._handle_helper_message(message)
        except:
            pass  # No data or pipe not connected
    
    def _handle_helper_message(self, message: str):
        """Handle message from audio helper."""
        self.log(f"Helper message: {message}")
        
        if message.startswith("WAKE:"):
            # Wake word detected
            self.log("Wake word detected via helper")
            # Send acknowledgment back
            self._send_to_helper("ACK:WAKE")
            
        elif message.startswith("COMMAND:"):
            # Command received
            command = message[8:]
            self.log(f"Command received: {command}")
            self._execute_command(command)
            
        elif message == "HEARTBEAT":
            # Helper heartbeat
            self._send_to_helper("ACK:HEARTBEAT")
    
    def _send_to_helper(self, message: str):
        """Send message to helper."""
        if self.pipe_handle:
            try:
                win32file.WriteFile(self.pipe_handle, message.encode('utf-8'))
            except:
                pass
    
    def _execute_command(self, command: str):
        """Execute command through existing system."""
        try:
            input_file = PROJECT_ROOT / "input.txt"
            with open(input_file, "w") as f:
                f.write(command.lower())
            self.log(f"Command written to input.txt")
        except Exception as e:
            self.log(f"Command execution failed: {e}")
    
    def _health_loop(self):
        """Health monitoring loop."""
        missed_heartbeats = 0
        
        while self.running:
            time.sleep(5)
            
            # Check helper
            if self.helper_process:
                if self.helper_process.poll() is not None:
                    missed_heartbeats += 1
                    if missed_heartbeats >= 3:
                        self.log("Helper unresponsive, restarting...")
                        self._start_helper()
                        missed_heartbeats = 0
                else:
                    missed_heartbeats = 0
            
            # Log status
            self.log(f"Health check: helper={'alive' if self.helper_process and self.helper_process.poll() is None else 'dead'}")
    
    def log(self, message: str):
        """Log to Windows Event Log and console."""
        try:
            servicemanager.LogInfoMsg(f"JARVIS: {message}")
        except:
            pass
        print(f"[JARVIS Service] {message}")


def install_service():
    """Install JARVIS as Windows Service."""
    if not PYWIN32_AVAILABLE:
        print("pywin32 required for Windows Service")
        return False
    
    try:
        # Install service
        win32serviceutil.InstallService(
            JarvisWindowsService._svc_class_name_,
            JarvisWindowsService._svc_name_,
            JarvisWindowsService._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            description=JarvisWindowsService._svc_description_
        )
        print(f"✓ Service '{JarvisWindowsService._svc_name_}' installed")
        
        # Configure recovery (auto-restart on crash)
        import subprocess
        subprocess.run([
            "sc", "failure", JarvisWindowsService._svc_name_,
            "reset=", "86400",
            "actions=", "restart/1000/restart/1000/restart/1000"
        ], capture_output=True)
        print("✓ Auto-restart on crash configured")
        
        return True
        
    except Exception as e:
        print(f"✗ Installation failed: {e}")
        return False


def uninstall_service():
    """Uninstall JARVIS Windows Service."""
    if not PYWIN32_AVAILABLE:
        return False
    
    try:
        win32serviceutil.RemoveService(JarvisWindowsService._svc_name_)
        print(f"✓ Service '{JarvisWindowsService._svc_name_}' removed")
        return True
    except Exception as e:
        print(f"✗ Removal failed: {e}")
        return False


def start_service():
    """Start the JARVIS service."""
    if not PYWIN32_AVAILABLE:
        return False
    
    try:
        win32serviceutil.StartService(JarvisWindowsService._svc_name_)
        print(f"✓ Service started")
        return True
    except Exception as e:
        print(f"✗ Start failed: {e}")
        return False


def stop_service():
    """Stop the JARVIS service."""
    if not PYWIN32_AVAILABLE:
        return False
    
    try:
        win32serviceutil.StopService(JarvisWindowsService._svc_name_)
        print(f"✓ Service stopped")
        return True
    except Exception as e:
        print(f"✗ Stop failed: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Running as service
        if PYWIN32_AVAILABLE:
            servicemanager.Initialize()
            servicemanager.PrepareToHostSingle(JarvisWindowsService)
            servicemanager.StartServiceCtrlDispatcher()
        else:
            print("pywin32 required")
    else:
        # Command line
        if PYWIN32_AVAILABLE:
            win32serviceutil.HandleCommandLine(JarvisWindowsService)
        else:
            print("pywin32 required")
