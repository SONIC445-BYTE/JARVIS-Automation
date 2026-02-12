import requests

def debug_tts(message: str, voice: str = "Matthew"):
    url = f"https://api.streamelements.com/kappa/v2/speech?voice={voice}&text={{{message}}}"
    headers = {'User-Agent':'Mozilla/5.0(Maciontosh;intel Mac OS X 10_15_7)AppleWebKit/537.36(KHTML,like Gecoko)Chrome/119.0.0.0 Safari/537.36'}
    
    print(f"Requesting URL: {url}")
    try:
        response = requests.get(url=url, headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Content Type: {response.headers.get('Content-Type')}")
        print(f"Content Length: {len(response.content)} bytes")
        
        sample = response.content[:100]
        print(f"First 100 bytes: {sample}")
        
        try:
            print(f"Content as text (if error): {response.content.decode('utf-8')}")
        except:
            print("Content is binary (likely audio)")
            
        if response.status_code == 200 and len(response.content) > 0:
            with open("debug_test.mp3", "wb") as f:
                f.write(response.content)
            print("Saved to debug_test.mp3")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_tts("Hello world")
