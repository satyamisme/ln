# REQUIRED CONFIG
BOT_TOKEN = "6629483853:AAGn1f7kwSh-d70aAMTC3ai-ZwDN5GSQQUo"
OWNER_ID = 7112950578
TELEGRAM_API = 25419896
TELEGRAM_HASH = "53bec45fc1e7131eae6d06a9e81ebc22"

# OPTIONAL CONFIG
USER_SESSION_STRING = ""  # Leave empty if not using user session
DOWNLOAD_DIR = "/usr/src/app/downloads/"
CMD_SUFFIX = ""
AUTHORIZED_CHATS = []  # Example: [-1001234567890, -1009876543210]
SUDO_USERS = [6972379132, 5512145984]# Telegram user IDs
DATABASE_URL = "mongodb+srv://leechanasty:Aa100200@cluster0.ch0nwn5.mongodb.net/?retryWrites=true&w=majority"
STATUS_LIMIT = 10
DEFAULT_UPLOAD = "gd"  # 'gd' for Google Drive, 'rc' for Rclone
STATUS_UPDATE_INTERVAL = 10
FILELION_API = ""
STREAMWISH_API = "21579znp9rc8yoknte732"
EXTENSION_FILTER = []  # Example: ['tmp', 'log', 'iso']  # blocked extensions
INCOMPLETE_TASK_NOTIFIER = True
YT_DLP_OPTIONS = ""  # e.g., "format=bestvideo+bestaudio"
USE_SERVICE_ACCOUNTS = True
NAME_SUBSTITUTE = ""  # e.g., "s/old/new/g" to rename files

# GDrive Tools
GDRIVE_ID = "1j4PTVteRSGnat9Oqx6tQoHG5mwCmho__"
IS_TEAM_DRIVE = False  # Set to True if using Team Drive
STOP_DUPLICATE = True
INDEX_URL = "https://leech.satyamismeaio.workers.dev/"

# Rclone
RCLONE_PATH = ""  # e.g., "remote:folder"
RCLONE_FLAGS = ""  # e.g., "--drive-chunk-size 64M"
RCLONE_SERVE_URL = ""
RCLONE_SERVE_PORT = 0
RCLONE_SERVE_USER = ""
RCLONE_SERVE_PASS = ""

# JDownloader
JD_EMAIL = "satyamisme@gmail.com"
JD_PASS = "Google@123"

# Sabnzbd
USENET_SERVERS = [
    {
        "name": "main",
        "host": "",
        "port": 5126,
        "timeout": 60,
        "username": "",
        "password": "",
        "connections": 8,
        "ssl": 1,
        "ssl_verify": 2,
        "ssl_ciphers": "",
        "enable": 1,
        "required": 0,
        "optional": 0,
        "retention": 0,
        "send_group": 0,
        "priority": 0,
    }
]

# Update
# UPSTREAM_REPO = "https://github.com/satyamisme/leech"
# UPSTREAM_BRANCH = "master"

# Leech
LEECH_SPLIT_SIZE = 0  # Auto (0) or manual size in bytes (e.g., 2147483648 for 2GB)
AS_DOCUMENT = True  # Upload as document (recommended for video/audio)
EQUAL_SPLITS = False  # Equal split size for multi-part
MEDIA_GROUP = True  # Group media in Telegram albums
USER_TRANSMISSION = False  # Use user session for upload
MIXED_LEECH = False  # Allow mixed upload modes
LEECH_FILENAME_PREFIX = ""  # Prefix for all leech files
LEECH_DUMP_CHAT = -1001845518274  # Log leech activity here
THUMBNAIL_LAYOUT = ""  # e.g., "portrait", "landscape"

# qBittorrent/Aria2c
TORRENT_TIMEOUT = 600  # Seconds to seed after download
BASE_URL = ""  # Required for external access (e.g., "https://yourdomain.com")
BASE_URL_PORT = 80  # Port for web UI
WEB_PINCODE = False  # Generate PIN for web UI

# Queueing system
QUEUE_ALL = 8  # Max total tasks
QUEUE_DOWNLOAD = 4  # Max concurrent downloads
QUEUE_UPLOAD = 2  # Max concurrent uploads

# RSS
RSS_DELAY = 600  # Check RSS every X seconds
RSS_CHAT = ""  # Send RSS results to this chat ID

# Torrent Search
SEARCH_API_LINK = ""  # For external search API
SEARCH_LIMIT = 10  # Max results per search
SEARCH_PLUGINS = [
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/piratebay.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/limetorrents.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torlock.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentscsv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/eztv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentproject.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/kickass_torrent.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/yts_am.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/linuxtracker.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/ettv.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/glotorrents.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/thepiratebay.py",
    "https://raw.githubusercontent.com/v1k45/1337x-qBittorrent-search-plugin/master/leetx.py",
    "https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/magnetdl.py",
    "https://raw.githubusercontent.com/msagca/qbittorrent_plugins/main/uniondht.py",
    "https://raw.githubusercontent.com/khensolomon/leyts/master/yts.py",
]
