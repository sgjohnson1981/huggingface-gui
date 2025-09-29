import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logging():
    """
    Configures the logging for the application.
    """
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_file = os.path.join(log_dir, "app.log")

    # Create a logger
    logger = logging.getLogger("HuggingFaceGUI")
    logger.setLevel(logging.INFO)

    # Prevent handlers from being added multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a rotating file handler
    handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=5)

    # Create a logging format
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(handler)

    return logger

# Global logger instance
logger = setup_logging()