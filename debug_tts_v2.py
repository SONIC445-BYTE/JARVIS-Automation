import requests

def debug_tts(message: str, voice: str = "Matthew"):
    # Trying without curly braces
    url = f"https://api.streamelements.com/kappa/v2/speech?voice={voice}&text={message}"
    headers = {'User-Agent':'Mozilla/5.0(Maciontosh;intel Mac OS X 10_15_7)AppleWebKit/537.36(KHTML,like Gecoko)Chrome/119.0.0.0 Safari/537.36'}
    
    print(f"Requesting URL: {url}")
    try:
        response = requests.get(url=url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.headers.get('Content-Type')}")
        
        if response.status_code == 200 and response.headers.get('Content-Type') == 'audio/mp3':
            print("Success! Got audio data.")
            with open("debug_test_success.mp3", "wb") as f:
                f.write(response.content)
            print("Saved to debug_test_success.mp3")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_tts("Hello testing")
