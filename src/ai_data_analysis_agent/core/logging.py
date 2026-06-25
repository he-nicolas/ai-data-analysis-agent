import logging
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Console handler
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter(
            "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
        ))

        # File handler
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        file_handler = logging.FileHandler(log_dir / "app.log")
        file_handler.setFormatter(logging.Formatter(
            "[%(asctime)s] %(name)s - %(levelname)s - %(message)s"
        ))

        logger.addHandler(console)
        logger.addHandler(file_handler)

    return logger