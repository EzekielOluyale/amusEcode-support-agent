import logging
import sys
from pathlib import Path
from datetime import datetime

# Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Logs Directory
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Log File
LOG_FILE = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
LOG_FILE_PATH = LOG_DIR / LOG_FILE

# Formatter
LOG_FORMAT = logging.Formatter(
    "[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s"
)

# File Handler
file_handler = logging.FileHandler(LOG_FILE_PATH)
file_handler.setFormatter(LOG_FORMAT)

# Console Handler
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(LOG_FORMAT)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
