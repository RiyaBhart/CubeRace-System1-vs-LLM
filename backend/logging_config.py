import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({'time': self.formatTime(record), 'level': record.levelname,
                           'logger': record.name, 'message': record.getMessage()})


def configure_logging(directory: Path):
    logger = logging.getLogger('backend')
    if logger.handlers:
        return
    directory.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(directory / 'calls.jsonl', maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    handler.setFormatter(JsonFormatter())
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)
    console.setFormatter(logging.Formatter('%(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.addHandler(console)
