"""
Phase 2c: machine-readable catalog of every platform name JARVIS can
recognize, generated from the Phase 2b audit (docs/adapter_audit.md).

This is the "known platform universe" used by the resolution gate
(AgentCore/resolution_gate.py) to distinguish "I recognize this platform
name but have no real adapter for it yet" (most of these 160 entries,
today) from "this text does not name a platform at all" (falls through
to normal chat/action classification unchanged).

classification is informational (from the audit: a=real/complete,
b=real-but-incomplete, c=fabricated/scaffold) -- it does NOT mean the
platform is actually controllable today. Whether a platform is actually
controllable is DAEMON_ADAPTER_FOR: only entries listed there have a
working daemon-contract adapter (platform_adapters/registry.py) wired
through CommandRouter today. Phase 2d ports more of the (a)/(b) folders
onto that contract over time; when a folder is ported, add it here.

Regenerate with: see docs/adapter_audit.md "Reproducing this audit".
"""
from typing import Dict, List, Optional, TypedDict


class PlatformInfo(TypedDict):
    display_name: str
    aliases: List[str]
    classification: str  # 'a' | 'b' | 'c', see docs/adapter_audit.md


# folder name (AgentCore/platform_adapters/<key>) -> info
PLATFORM_CATALOG: Dict[str, PlatformInfo] = {
    "acorns": {
        "display_name": "Acorns",
        "aliases": [
            "acorns"
        ],
        "classification": "c"
    },
    "activecampaign": {
        "display_name": "ActiveCampaign",
        "aliases": [
            "activecampaign"
        ],
        "classification": "c"
    },
    "adobe_acrobat": {
        "display_name": "Adobe Acrobat",
        "aliases": [
            "adobe acrobat"
        ],
        "classification": "c"
    },
    "airbnb": {
        "display_name": "Airbnb",
        "aliases": [
            "airbnb"
        ],
        "classification": "c"
    },
    "airtable": {
        "display_name": "Airtable",
        "aliases": [
            "airtable"
        ],
        "classification": "c"
    },
    "alibaba": {
        "display_name": "Alibaba",
        "aliases": [
            "alibaba"
        ],
        "classification": "c"
    },
    "alibaba_cloud": {
        "display_name": "Alibaba Cloud",
        "aliases": [
            "alibaba cloud"
        ],
        "classification": "c"
    },
    "amazon": {
        "display_name": "Amazon",
        "aliases": [
            "amazon"
        ],
        "classification": "a"
    },
    "android_studio": {
        "display_name": "Android Studio",
        "aliases": [
            "android studio"
        ],
        "classification": "c"
    },
    "appletv": {
        "display_name": "Apple TV+",
        "aliases": [
            "apple tv+",
            "appletv"
        ],
        "classification": "c"
    },
    "arduino_ide": {
        "display_name": "Arduino IDE",
        "aliases": [
            "arduino ide"
        ],
        "classification": "c"
    },
    "asana": {
        "display_name": "Asana",
        "aliases": [
            "asana"
        ],
        "classification": "c"
    },
    "aws": {
        "display_name": "AWS",
        "aliases": [
            "aws"
        ],
        "classification": "c"
    },
    "azure": {
        "display_name": "Microsoft Azure",
        "aliases": [
            "azure",
            "microsoft azure"
        ],
        "classification": "c"
    },
    "basecamp": {
        "display_name": "Basecamp",
        "aliases": [
            "basecamp"
        ],
        "classification": "c"
    },
    "betterment": {
        "display_name": "Betterment",
        "aliases": [
            "betterment"
        ],
        "classification": "c"
    },
    "bigcommerce": {
        "display_name": "BigCommerce",
        "aliases": [
            "bigcommerce"
        ],
        "classification": "c"
    },
    "bitbucket": {
        "display_name": "Bitbucket",
        "aliases": [
            "bitbucket"
        ],
        "classification": "c"
    },
    "blackboard": {
        "display_name": "Blackboard",
        "aliases": [
            "blackboard"
        ],
        "classification": "c"
    },
    "booking": {
        "display_name": "Booking.com",
        "aliases": [
            "booking",
            "booking.com"
        ],
        "classification": "c"
    },
    "bumble": {
        "display_name": "Bumble",
        "aliases": [
            "bumble"
        ],
        "classification": "c"
    },
    "calculator": {
        "display_name": "Calculator",
        "aliases": [
            "calculator"
        ],
        "classification": "b"
    },
    "calm": {
        "display_name": "Calm",
        "aliases": [
            "calm"
        ],
        "classification": "c"
    },
    "canvas": {
        "display_name": "Canvas",
        "aliases": [
            "canvas"
        ],
        "classification": "c"
    },
    "cashapp": {
        "display_name": "Cash App",
        "aliases": [
            "cash app",
            "cashapp"
        ],
        "classification": "c"
    },
    "chargebee": {
        "display_name": "Chargebee",
        "aliases": [
            "chargebee"
        ],
        "classification": "c"
    },
    "chime": {
        "display_name": "Chime",
        "aliases": [
            "chime"
        ],
        "classification": "c"
    },
    "chrome": {
        "display_name": "Google Chrome",
        "aliases": [
            "chrome",
            "google chrome"
        ],
        "classification": "a"
    },
    "circleci": {
        "display_name": "CircleCI",
        "aliases": [
            "circleci"
        ],
        "classification": "c"
    },
    "clickup": {
        "display_name": "ClickUp",
        "aliases": [
            "clickup"
        ],
        "classification": "c"
    },
    "coinbase": {
        "display_name": "Coinbase",
        "aliases": [
            "coinbase"
        ],
        "classification": "c"
    },
    "coursera": {
        "display_name": "Coursera",
        "aliases": [
            "coursera"
        ],
        "classification": "c"
    },
    "datadog": {
        "display_name": "Datadog",
        "aliases": [
            "datadog"
        ],
        "classification": "c"
    },
    "delta": {
        "display_name": "Delta",
        "aliases": [
            "delta"
        ],
        "classification": "c"
    },
    "discord": {
        "display_name": "Discord",
        "aliases": [
            "discord"
        ],
        "classification": "c"
    },
    "disneyplus": {
        "display_name": "Disney+",
        "aliases": [
            "disney+",
            "disneyplus"
        ],
        "classification": "c"
    },
    "dynamics365": {
        "display_name": "Microsoft Dynamics 365",
        "aliases": [
            "dynamics365",
            "microsoft dynamics 365"
        ],
        "classification": "c"
    },
    "ebay": {
        "display_name": "eBay",
        "aliases": [
            "ebay"
        ],
        "classification": "c"
    },
    "edx": {
        "display_name": "edX",
        "aliases": [
            "edx"
        ],
        "classification": "c"
    },
    "eloqua": {
        "display_name": "Eloqua",
        "aliases": [
            "eloqua"
        ],
        "classification": "c"
    },
    "epic_games": {
        "display_name": "Epic Games Store",
        "aliases": [
            "epic games",
            "epic games store"
        ],
        "classification": "c"
    },
    "etrade": {
        "display_name": "E*Trade",
        "aliases": [
            "e*trade",
            "etrade"
        ],
        "classification": "c"
    },
    "etsy": {
        "display_name": "Etsy",
        "aliases": [
            "etsy"
        ],
        "classification": "c"
    },
    "expedia": {
        "display_name": "Expedia",
        "aliases": [
            "expedia"
        ],
        "classification": "c"
    },
    "explorer": {
        "display_name": "Windows Explorer",
        "aliases": [
            "explorer",
            "windows explorer"
        ],
        "classification": "b"
    },
    "facebook": {
        "display_name": "Facebook",
        "aliases": [
            "facebook"
        ],
        "classification": "c"
    },
    "fidelity": {
        "display_name": "Fidelity",
        "aliases": [
            "fidelity"
        ],
        "classification": "c"
    },
    "fitbit": {
        "display_name": "Fitbit",
        "aliases": [
            "fitbit"
        ],
        "classification": "c"
    },
    "freshsales": {
        "display_name": "Freshsales",
        "aliases": [
            "freshsales"
        ],
        "classification": "c"
    },
    "gcp": {
        "display_name": "Google Cloud Platform",
        "aliases": [
            "gcp",
            "google cloud platform"
        ],
        "classification": "c"
    },
    "git_cli": {
        "display_name": "Git CLI",
        "aliases": [
            "git cli"
        ],
        "classification": "c"
    },
    "github": {
        "display_name": "GitHub",
        "aliases": [
            "github"
        ],
        "classification": "c"
    },
    "github_desktop": {
        "display_name": "GitHub Desktop",
        "aliases": [
            "github desktop"
        ],
        "classification": "c"
    },
    "gitlab": {
        "display_name": "GitLab",
        "aliases": [
            "gitlab"
        ],
        "classification": "c"
    },
    "gmail": {
        "display_name": "Gmail",
        "aliases": [
            "gmail"
        ],
        "classification": "b"
    },
    "google": {
        "display_name": "Google Search",
        "aliases": [
            "google",
            "google search"
        ],
        "classification": "a"
    },
    "google_classroom": {
        "display_name": "Google Classroom",
        "aliases": [
            "google classroom"
        ],
        "classification": "c"
    },
    "hbomax": {
        "display_name": "HBO Max",
        "aliases": [
            "hbo max",
            "hbomax"
        ],
        "classification": "c"
    },
    "headspace": {
        "display_name": "Headspace",
        "aliases": [
            "headspace"
        ],
        "classification": "c"
    },
    "hinge": {
        "display_name": "Hinge",
        "aliases": [
            "hinge"
        ],
        "classification": "c"
    },
    "hubspot": {
        "display_name": "HubSpot",
        "aliases": [
            "hubspot"
        ],
        "classification": "c"
    },
    "hulu": {
        "display_name": "Hulu",
        "aliases": [
            "hulu"
        ],
        "classification": "c"
    },
    "ibm_cloud": {
        "display_name": "IBM Cloud",
        "aliases": [
            "ibm cloud"
        ],
        "classification": "c"
    },
    "instagram": {
        "display_name": "Instagram",
        "aliases": [
            "instagram"
        ],
        "classification": "c"
    },
    "jdcom": {
        "display_name": "JD.com",
        "aliases": [
            "jd.com",
            "jdcom"
        ],
        "classification": "c"
    },
    "jenkins": {
        "display_name": "Jenkins",
        "aliases": [
            "jenkins"
        ],
        "classification": "c"
    },
    "jira": {
        "display_name": "Jira",
        "aliases": [
            "jira"
        ],
        "classification": "c"
    },
    "khan_academy": {
        "display_name": "Khan Academy",
        "aliases": [
            "khan academy"
        ],
        "classification": "c"
    },
    "klaviyo": {
        "display_name": "Klaviyo",
        "aliases": [
            "klaviyo"
        ],
        "classification": "c"
    },
    "line": {
        "display_name": "LINE",
        "aliases": [
            "line"
        ],
        "classification": "c"
    },
    "linkedin": {
        "display_name": "LinkedIn",
        "aliases": [
            "linkedin"
        ],
        "classification": "c"
    },
    "lm_studio": {
        "display_name": "LM Studio",
        "aliases": [
            "lm studio"
        ],
        "classification": "c"
    },
    "lyft": {
        "display_name": "Lyft",
        "aliases": [
            "lyft"
        ],
        "classification": "c"
    },
    "magento": {
        "display_name": "Magento",
        "aliases": [
            "magento"
        ],
        "classification": "c"
    },
    "mailchimp": {
        "display_name": "Mailchimp",
        "aliases": [
            "mailchimp"
        ],
        "classification": "c"
    },
    "marketo": {
        "display_name": "Marketo",
        "aliases": [
            "marketo"
        ],
        "classification": "c"
    },
    "mattermost": {
        "display_name": "Mattermost",
        "aliases": [
            "mattermost"
        ],
        "classification": "c"
    },
    "meetup": {
        "display_name": "Meetup",
        "aliases": [
            "meetup"
        ],
        "classification": "c"
    },
    "mercadolibre": {
        "display_name": "Mercado Libre",
        "aliases": [
            "mercado libre",
            "mercadolibre"
        ],
        "classification": "c"
    },
    "microsoft_teams": {
        "display_name": "Microsoft Teams",
        "aliases": [
            "microsoft teams"
        ],
        "classification": "c"
    },
    "monday": {
        "display_name": "Monday.com",
        "aliases": [
            "monday",
            "monday.com"
        ],
        "classification": "c"
    },
    "moodle": {
        "display_name": "Moodle",
        "aliases": [
            "moodle"
        ],
        "classification": "c"
    },
    "ms_excel": {
        "display_name": "Microsoft Excel",
        "aliases": [
            "microsoft excel",
            "ms excel"
        ],
        "classification": "c"
    },
    "ms_powerpoint": {
        "display_name": "Microsoft PowerPoint",
        "aliases": [
            "microsoft powerpoint",
            "ms powerpoint"
        ],
        "classification": "c"
    },
    "ms_word": {
        "display_name": "Microsoft Word",
        "aliases": [
            "microsoft word",
            "ms word"
        ],
        "classification": "c"
    },
    "myfitnesspal": {
        "display_name": "MyFitnessPal",
        "aliases": [
            "myfitnesspal"
        ],
        "classification": "c"
    },
    "netflix": {
        "display_name": "Netflix",
        "aliases": [
            "netflix"
        ],
        "classification": "c"
    },
    "new_relic": {
        "display_name": "New Relic",
        "aliases": [
            "new relic"
        ],
        "classification": "c"
    },
    "nintendo": {
        "display_name": "Nintendo eShop",
        "aliases": [
            "nintendo",
            "nintendo eshop"
        ],
        "classification": "c"
    },
    "nodejs_runtime": {
        "display_name": "Node.js Runtime",
        "aliases": [
            "node.js runtime",
            "nodejs runtime"
        ],
        "classification": "c"
    },
    "notepad": {
        "display_name": "Notepad",
        "aliases": [
            "notepad"
        ],
        "classification": "b"
    },
    "notion": {
        "display_name": "Notion",
        "aliases": [
            "notion"
        ],
        "classification": "c"
    },
    "okcupid": {
        "display_name": "OkCupid",
        "aliases": [
            "okcupid"
        ],
        "classification": "c"
    },
    "ollama": {
        "display_name": "Ollama",
        "aliases": [
            "ollama"
        ],
        "classification": "c"
    },
    "onedrive": {
        "display_name": "Microsoft OneDrive",
        "aliases": [
            "microsoft onedrive",
            "onedrive"
        ],
        "classification": "c"
    },
    "oracle_cloud": {
        "display_name": "Oracle Cloud",
        "aliases": [
            "oracle cloud"
        ],
        "classification": "c"
    },
    "outlook": {
        "display_name": "Outlook",
        "aliases": [
            "outlook"
        ],
        "classification": "c"
    },
    "pagerduty": {
        "display_name": "PagerDuty",
        "aliases": [
            "pagerduty"
        ],
        "classification": "c"
    },
    "pardot": {
        "display_name": "Pardot",
        "aliases": [
            "pardot"
        ],
        "classification": "c"
    },
    "paypal": {
        "display_name": "PayPal",
        "aliases": [
            "paypal"
        ],
        "classification": "c"
    },
    "peloton": {
        "display_name": "Peloton",
        "aliases": [
            "peloton"
        ],
        "classification": "c"
    },
    "pinterest": {
        "display_name": "Pinterest",
        "aliases": [
            "pinterest"
        ],
        "classification": "c"
    },
    "pipedrive": {
        "display_name": "Pipedrive",
        "aliases": [
            "pipedrive"
        ],
        "classification": "c"
    },
    "playstation": {
        "display_name": "PlayStation Network",
        "aliases": [
            "playstation",
            "playstation network"
        ],
        "classification": "c"
    },
    "prime_video": {
        "display_name": "Amazon Prime Video",
        "aliases": [
            "amazon prime video",
            "prime video"
        ],
        "classification": "c"
    },
    "protonmail": {
        "display_name": "ProtonMail",
        "aliases": [
            "protonmail"
        ],
        "classification": "c"
    },
    "pycharm": {
        "display_name": "PyCharm",
        "aliases": [
            "pycharm"
        ],
        "classification": "c"
    },
    "python_runtime": {
        "display_name": "Python Runtime",
        "aliases": [
            "python runtime"
        ],
        "classification": "c"
    },
    "qq": {
        "display_name": "QQ",
        "aliases": [
            "qq"
        ],
        "classification": "c"
    },
    "rakuten": {
        "display_name": "Rakuten",
        "aliases": [
            "rakuten"
        ],
        "classification": "c"
    },
    "recharge": {
        "display_name": "Recharge",
        "aliases": [
            "recharge"
        ],
        "classification": "c"
    },
    "reddit": {
        "display_name": "Reddit",
        "aliases": [
            "reddit"
        ],
        "classification": "c"
    },
    "revolut": {
        "display_name": "Revolut",
        "aliases": [
            "revolut"
        ],
        "classification": "c"
    },
    "robinhood": {
        "display_name": "Robinhood",
        "aliases": [
            "robinhood"
        ],
        "classification": "c"
    },
    "roblox": {
        "display_name": "Roblox",
        "aliases": [
            "roblox"
        ],
        "classification": "c"
    },
    "salesforce": {
        "display_name": "Salesforce",
        "aliases": [
            "salesforce"
        ],
        "classification": "c"
    },
    "sap_sales": {
        "display_name": "SAP Sales Cloud",
        "aliases": [
            "sap sales",
            "sap sales cloud"
        ],
        "classification": "c"
    },
    "schoology": {
        "display_name": "Schoology",
        "aliases": [
            "schoology"
        ],
        "classification": "c"
    },
    "schwab": {
        "display_name": "Charles Schwab",
        "aliases": [
            "charles schwab",
            "schwab"
        ],
        "classification": "c"
    },
    "servicenow": {
        "display_name": "ServiceNow",
        "aliases": [
            "servicenow"
        ],
        "classification": "c"
    },
    "shopify": {
        "display_name": "Shopify",
        "aliases": [
            "shopify"
        ],
        "classification": "c"
    },
    "skype": {
        "display_name": "Skype",
        "aliases": [
            "skype"
        ],
        "classification": "c"
    },
    "slack": {
        "display_name": "Slack",
        "aliases": [
            "slack"
        ],
        "classification": "c"
    },
    "smartsheet": {
        "display_name": "Smartsheet",
        "aliases": [
            "smartsheet"
        ],
        "classification": "c"
    },
    "snapchat": {
        "display_name": "Snapchat",
        "aliases": [
            "snapchat"
        ],
        "classification": "c"
    },
    "splunk": {
        "display_name": "Splunk",
        "aliases": [
            "splunk"
        ],
        "classification": "c"
    },
    "spotify": {
        "display_name": "Spotify",
        "aliases": [
            "spotify"
        ],
        "classification": "b"
    },
    "square": {
        "display_name": "Square",
        "aliases": [
            "square"
        ],
        "classification": "c"
    },
    "steam": {
        "display_name": "Steam",
        "aliases": [
            "steam"
        ],
        "classification": "c"
    },
    "strava": {
        "display_name": "Strava",
        "aliases": [
            "strava"
        ],
        "classification": "c"
    },
    "stripe": {
        "display_name": "Stripe",
        "aliases": [
            "stripe"
        ],
        "classification": "c"
    },
    "teladoc": {
        "display_name": "Teladoc",
        "aliases": [
            "teladoc"
        ],
        "classification": "c"
    },
    "telegram": {
        "display_name": "Telegram",
        "aliases": [
            "telegram"
        ],
        "classification": "c"
    },
    "tiktok": {
        "display_name": "TikTok",
        "aliases": [
            "tiktok"
        ],
        "classification": "c"
    },
    "tinder": {
        "display_name": "Tinder",
        "aliases": [
            "tinder"
        ],
        "classification": "c"
    },
    "travisci": {
        "display_name": "Travis CI",
        "aliases": [
            "travis ci",
            "travisci"
        ],
        "classification": "c"
    },
    "trello": {
        "display_name": "Trello",
        "aliases": [
            "trello"
        ],
        "classification": "c"
    },
    "twitch": {
        "display_name": "Twitch",
        "aliases": [
            "twitch"
        ],
        "classification": "c"
    },
    "twitter": {
        "display_name": "Twitter/X",
        "aliases": [
            "twitter",
            "twitter/x"
        ],
        "classification": "b"
    },
    "uber": {
        "display_name": "Uber",
        "aliases": [
            "uber"
        ],
        "classification": "c"
    },
    "udemy": {
        "display_name": "Udemy",
        "aliases": [
            "udemy"
        ],
        "classification": "c"
    },
    "unity": {
        "display_name": "Unity",
        "aliases": [
            "unity"
        ],
        "classification": "c"
    },
    "unreal_engine": {
        "display_name": "Unreal Engine",
        "aliases": [
            "unreal engine"
        ],
        "classification": "c"
    },
    "venmo": {
        "display_name": "Venmo",
        "aliases": [
            "venmo"
        ],
        "classification": "c"
    },
    "viber": {
        "display_name": "Viber",
        "aliases": [
            "viber"
        ],
        "classification": "c"
    },
    "vimeo": {
        "display_name": "Vimeo",
        "aliases": [
            "vimeo"
        ],
        "classification": "c"
    },
    "vkontakte": {
        "display_name": "VKontakte",
        "aliases": [
            "vkontakte"
        ],
        "classification": "c"
    },
    "vscode": {
        "display_name": "VS Code",
        "aliases": [
            "vs code",
            "vscode"
        ],
        "classification": "c"
    },
    "walmart": {
        "display_name": "Walmart Marketplace",
        "aliases": [
            "walmart",
            "walmart marketplace"
        ],
        "classification": "c"
    },
    "wealthfront": {
        "display_name": "Wealthfront",
        "aliases": [
            "wealthfront"
        ],
        "classification": "c"
    },
    "wechat": {
        "display_name": "WeChat",
        "aliases": [
            "wechat"
        ],
        "classification": "c"
    },
    "whatsapp": {
        "display_name": "WhatsApp",
        "aliases": [
            "whatsapp"
        ],
        "classification": "b"
    },
    "winrar": {
        "display_name": "WinRAR",
        "aliases": [
            "winrar"
        ],
        "classification": "c"
    },
    "wise": {
        "display_name": "Wise",
        "aliases": [
            "wise"
        ],
        "classification": "c"
    },
    "woocommerce": {
        "display_name": "WooCommerce",
        "aliases": [
            "woocommerce"
        ],
        "classification": "c"
    },
    "wrike": {
        "display_name": "Wrike",
        "aliases": [
            "wrike"
        ],
        "classification": "c"
    },
    "xbox_live": {
        "display_name": "Xbox Live",
        "aliases": [
            "xbox live"
        ],
        "classification": "c"
    },
    "youtube": {
        "display_name": "YouTube",
        "aliases": [
            "youtube"
        ],
        "classification": "b"
    },
    "zoho_crm": {
        "display_name": "Zoho CRM",
        "aliases": [
            "zoho crm"
        ],
        "classification": "c"
    },
    "zoom": {
        "display_name": "Zoom",
        "aliases": [
            "zoom"
        ],
        "classification": "c"
    }
}


# folder name -> working daemon adapter key (platform_adapters/registry.py),
# for the platforms that actually have a real, wired adapter today.
DAEMON_ADAPTER_FOR: Dict[str, str] = {
    "chrome": "browser",
    "notepad": "text_editor",
    "whatsapp": "whatsapp_desktop",
    "telegram": "telegram_desktop",
    "gmail": "gmail_browser",
    # Phase 2d: ported adapters (docs/adapter_audit.md class a/b folders).
    "amazon": "amazon",
    "google": "google",
    "calculator": "calculator",
    "explorer": "explorer",
    "twitter": "twitter",
    "spotify": "spotify",
    "youtube": "youtube",
}


def find_catalog_entry(text_lower: str) -> Optional[str]:
    """Return the catalog key (folder name) whose alias is the longest
    match found in text_lower, or None if no platform name is mentioned."""
    best_key: Optional[str] = None
    best_alias = ""
    for key, info in PLATFORM_CATALOG.items():
        for alias in info["aliases"]:
            if alias in text_lower and len(alias) > len(best_alias):
                best_key = key
                best_alias = alias
    return best_key
