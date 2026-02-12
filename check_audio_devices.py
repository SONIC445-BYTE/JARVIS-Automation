import sounddevice as sd

print("Available Audio Devices:")
print("========================")
print(sd.query_devices())

default_input = sd.default.device[0]
print(f"\nDefault Input Device Index: {default_input}")

try:
    device_info = sd.query_devices(default_input, 'input')
    print(f"Default Device Name: {device_info['name']}")
    print(f"Default Sample Rate: {device_info['default_samplerate']}")
except Exception as e:
    print(f"Error getting device info: {e}")
