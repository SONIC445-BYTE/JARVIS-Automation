"""
Simple test to verify WhatsApp automation logic without running full J.A.R.V.I.S
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now import
from Whatsapp_automation.wa import send_msg_wa

print("Testing WhatsApp automation...")
print("This will call send_msg_wa() which will:")
print("1. Ask for recipient")
print("2. Ask for message")
print("3. Send via WhatsApp Web")
print("\nMake sure you have input.txt being updated by the STT system")
print("Or manually edit input.txt to test\n")

# Call the function
send_msg_wa()
