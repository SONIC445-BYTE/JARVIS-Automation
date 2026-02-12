import re

# (pattern, intent, confidence)
RULES = [
    (re.compile(r'^\s*(jarvis[, ]+)?(delete|remove|erase)\b', re.I), ("SYSTEM_DELETE", 0.95)),
    (re.compile(r'^\s*(jarvis[, ]+)?(write|create|generate|implement|build)\b', re.I), ("CODING", 0.9)),
    (re.compile(r'\b(open|start|launch)\s+(vscode|code|android studio|idea)\b', re.I), ("OPEN_IDE", 0.9)),
    (re.compile(r'\b(upload|attach|send)\b.*\b(whatsapp|telegram|drive|gmail|photos)\b', re.I), ("EXECUTE_LOCAL", 0.9)),
    (re.compile(r'^\s*(jarvis|wake up|wake)\b', re.I), ("WAKE", 0.95)),
    (re.compile(r'\b(go to sleep|sleep|stop listening)\b', re.I), ("SLEEP", 0.95)),
]

def match_rules(text):
    text = text.strip()
    for patt, (intent, conf) in RULES:
        if patt.search(text):
            return intent, conf, "rule"
    return None, 0.0, None
