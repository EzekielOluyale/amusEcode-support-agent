import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Project Root
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Logs Directory
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Keep a static name for rotation, instead of timestamps
LOG_FILE_PATH = LOG_DIR / "agent.log"

# custom Formatter
LOG_FORMAT = logging.Formatter(
    "[%(asctime)s] %(lineno)d %(name)s - %(levelname)s - %(message)s"
)

def setup_logger(name=__name__):
    """Sets up a production-ready rotating logger."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Prevent adding handlers multiple times if imported in multiple files
    if not logger.handlers:
        # File Handler: Max 5MB per file, keeps the last 3 files
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH, 
            maxBytes=5*1024*1024, 
            backupCount=3
        )
        file_handler.setFormatter(LOG_FORMAT)

        # Console Handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(LOG_FORMAT)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger