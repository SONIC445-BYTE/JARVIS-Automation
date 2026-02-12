import webbrowser
from Automation.Web_Data import websites

def openweb(webname):
    print(f"DEBUG openweb received: '{webname}'")
    website_name = webname.lower().split()
    print(f"DEBUG Split words: {website_name}")
    counts = {}
    for name in website_name:
        counts[name] = counts.get(name,0) + 1
    urls_to_open = []
    for name,count in counts.items():
        if name in websites:
            print(f"DEBUG Found match: '{name}' -> '{websites[name]}'")
            urls_to_open.extend([websites[name]]*count)
        else:
            print(f"DEBUG No match for: '{name}'")
    print(f"DEBUG URLs to open: {urls_to_open}")
    for url in urls_to_open:
        webbrowser.open(url) 
    if urls_to_open:
        print("opening...")
    else:
        print("DEBUG: No URLs found to open!")