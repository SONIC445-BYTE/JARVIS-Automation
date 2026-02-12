"""
Service Installer - Windows Startup for jarvis.py --service
=============================================================
Adds JARVIS persistent wake mode to Windows startup.
"""

import os
import sys
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
JARVIS_PATH = PROJECT_ROOT / "jarvis.py"


def get_python_path() -> str:
    """Get current Python interpreter path."""
    return sys.executable


def install_startup():
    """Add JARVIS --service to Windows Startup (registry)."""
    import winreg
    
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        
        python_path = get_python_path()
        command = f'"{python_path}" "{JARVIS_PATH}" --service'
        
        winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        
        print("✓ JARVIS added to Windows Startup")
        print(f"  Command: python jarvis.py --service")
        print(f"  JARVIS will start automatically on login")
        return True
        
    except Exception as e:
        print(f"✗ Failed to add to startup: {e}")
        return False


def uninstall_startup():
    """Remove JARVIS from Windows Startup."""
    import winreg
    
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        
        try:
            winreg.DeleteValue(key, "JARVIS")
            print("✓ JARVIS removed from Windows Startup")
        except FileNotFoundError:
            print("JARVIS was not in startup")
        
        winreg.CloseKey(key)
        return True
        
    except Exception as e:
        print(f"✗ Failed to remove from startup: {e}")
        return False


def check_status():
    """Check if JARVIS is installed in startup."""
    print("Checking JARVIS installation status...")
    print()
    
    # Check startup registry
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_READ
        )
        try:
            value, _ = winreg.QueryValueEx(key, "JARVIS")
            print(f"✓ Windows Startup: INSTALLED")
            print(f"  Command: {value}")
        except FileNotFoundError:
            print("✗ Windows Startup: NOT installed")
        winreg.CloseKey(key)
    except Exception as e:
        print(f"✗ Cannot check startup: {e}")
    
    print()
    print("To run manually:")
    print(f"  python jarvis.py --service")


def run_service():
    """Run jarvis.py --service directly."""
    python_path = get_python_path()
    subprocess.run([python_path, str(JARVIS_PATH), "--service"])


def main():
    """CLI for service installer."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="JARVIS Service Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m WakeService.service_installer install   # Add to Windows Startup
  python -m WakeService.service_installer uninstall # Remove from Startup
  python -m WakeService.service_installer status    # Check installation
  python -m WakeService.service_installer run       # Run service now
        """
    )
    parser.add_argument(
        "command", 
        choices=["install", "uninstall", "status", "run"],
        help="Action to perform"
    )
    
    args = parser.parse_args()
    
    if args.command == "install":
        print("Installing JARVIS to Windows Startup...")
        print()
        install_startup()
            
    elif args.command == "uninstall":
        print("Removing JARVIS from Windows Startup...")
        print()
        uninstall_startup()
        
    elif args.command == "status":
        check_status()
        
    elif args.command == "run":
        run_service()


if __name__ == "__main__":
    main()
