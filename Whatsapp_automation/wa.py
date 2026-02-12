import pywhatkit as kit
import datetime
from TextToSpeech.Fast_DF_TTS import speak
from os import getcwd
import time
import threading

# Contact dictionary - Add more contacts here
contacts = {
    "myself": "+918240346272" # Example
}

def clear_file():
    file_path = f"{getcwd()}\\input.txt"
    with open(file_path,"w") as file:
        file.truncate(0)
    print(f"DEBUG: Cleared {file_path}", flush=True)

def speak_async(text):
    """Non-blocking speak - runs in background thread"""
    t = threading.Thread(target=speak, args=(text,))
    t.daemon = True  # Won't block program exit
    t.start()
    time.sleep(0.5)  # Give it a moment to start speaking

def send_msg_wa():
    print("DEBUG: send_msg_wa() called", flush=True)
    print("DEBUG: About to clear file and speak...", flush=True)
    clear_file()
    speak_async("Who do you want to send a message to, sir?")
    print("DEBUG: Speak started (async), now entering recipient loop...", flush=True)
    output_text = ""
    
    # Wait for recipient name
    print("DEBUG: Waiting for recipient input...", flush=True)
    while True:
        file_path = f"{getcwd()}\\input.txt"
        with open(file_path,"r") as file:
            input_text = file.read().lower().strip()
        
        # Only print every second to reduce spam
        if input_text:
            print(f"DEBUG: Read from file: '{input_text}'", flush=True)
        
        if input_text != output_text and input_text:
            output_text = input_text
            
            print(f"DEBUG: Input: {output_text}")
            # Check if input contains a known contact
            recipient_number = None
            recipient_name = None
            
            for name, number in contacts.items():
                if name in output_text:
                    recipient_number = number
                    recipient_name = name
                    break
            
            print(f"DEBUG: Recipient: {recipient_name}", flush=True)

            if recipient_number:
                print("DEBUG: Found recipient, asking for message...", flush=True)
                speak_async(f"Message to {recipient_name}. What is the message?")
                clear_file()
                message_has_been_sent = False
                output_text = ""  # Reset for message input
                
                # Wait for message content
                print("DEBUG: Waiting for message input...", flush=True)
                while not message_has_been_sent:
                     file_path = f"{getcwd()}\\input.txt"
                     with open(file_path,"r") as file:
                        msg_input = file.read().lower().strip()
                     
                     if msg_input:
                         print(f"DEBUG: Read message from file: '{msg_input}'", flush=True)
                     
                     if msg_input != output_text and msg_input:
                        print(f"DEBUG: Message Input: {msg_input}", flush=True)
                        # Logic to capture message. Assumes everything after "message is" or just the raw input is the message
                        # Verify it's not the previous command
                        if "message is" in msg_input:
                            message = msg_input.split("message is")[-1].strip()
                        else:
                             # Fallback: treat the whole input as message if it's not a control command
                             message = msg_input
                        
                        if message:
                            print(f"DEBUG: Sending message: {message}", flush=True)
                            speak_async(f"Sending message: {message}")
                            try:
                                # Use instant send with 30 second delay for WhatsApp to fully load
                                # tab_close=False so we can see if it worked
                                print("DEBUG: Opening WhatsApp Web and waiting 30 seconds...", flush=True)
                                kit.sendwhatmsg_instantly(recipient_number, message, wait_time=30, tab_close=False)
                                print("DEBUG: pywhatkit completed, message should be sent", flush=True)
                                speak_async("Message sent successfully")
                                message_has_been_sent = True
                                clear_file()
                                return
                            except Exception as e:
                                speak_async(f"Failed to send message. Error: {e}")
                                print(f"Error: {e}", flush=True)
                                return
                        
                        output_text = msg_input # Update state
                     
                     time.sleep(0.5)  # Prevent CPU spinning
            
            elif "cancel" in output_text:
                speak_async("Cancelled WhatsApp message.")
                return

            else:
                # Feedback if valid input but no contact found
                if "send to" in output_text:
                    speak("Contact not found. Please try again or check the list.")
                    print(f"Available contacts: {list(contacts.keys())}")
        
        time.sleep(0.5)  # Prevent CPU spinning
                                 

