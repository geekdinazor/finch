import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


CONFIG_PATH   = str(Path.home() / ".config" / "finch")
SETTINGS_FILE = os.path.join(CONFIG_PATH, "settings.json")


class ObjectType(str, Enum):
    BUCKET = "Bucket"
    FOLDER = "Folder"
    FILE   = "File"


@dataclass
class Settings:
    """Application settings with load/save/apply_logging lifecycle."""

    check_folder_contents: bool = True
    datetime_format:       str  = "%d %b %Y %H:%M"

    logging_enabled: bool = False
    logging_to_file: bool = False
    log_file_path:   str  = os.path.join(CONFIG_PATH, "finch.log")
    logger_levels:   dict = field(default_factory=lambda: {
        "keyring.backend":   "WARNING",
        "botocore.hooks":    "DEBUG",
        "botocore.loaders":  "ERROR",
        "botocore.endpoint": "DEBUG",
        "botocore.client":   "INFO",
        "botocore.regions":  "ERROR",
        "botocore.parsers":  "DEBUG",
        "finch":             "DEBUG",
    })

    def load(self) -> None:
        try:
            with open(SETTINGS_FILE) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return
        self.check_folder_contents = bool(data.get("check_folder_contents", self.check_folder_contents))
        self.datetime_format       = data.get("datetime_format", self.datetime_format)
        self.logging_enabled       = bool(data.get("logging_enabled", self.logging_enabled))
        self.logging_to_file       = bool(data.get("logging_to_file", self.logging_to_file))
        self.log_file_path         = data.get("log_file_path", self.log_file_path)
        self.logger_levels.update(data.get("logger_levels", {}))

    def save(self) -> None:
        with open(SETTINGS_FILE, "w") as f:
            json.dump({
                "check_folder_contents": self.check_folder_contents,
                "datetime_format":       self.datetime_format,
                "logging_enabled":       self.logging_enabled,
                "logging_to_file":       self.logging_to_file,
                "log_file_path":         self.log_file_path,
                "logger_levels":         self.logger_levels,
            }, f, indent=2)

    def apply_logging(self) -> None:
        root = logging.getLogger()
        for h in root.handlers[:]:
            root.removeHandler(h)
        fmt = logging.Formatter("%(name)s %(levelname)s %(message)s")
        if self.logging_enabled:
            root.setLevel(logging.DEBUG)
            sh = logging.StreamHandler()
            sh.setFormatter(fmt)
            root.addHandler(sh)
            if self.logging_to_file and self.log_file_path:
                fh = logging.FileHandler(self.log_file_path)
                fh.setFormatter(fmt)
                root.addHandler(fh)
            for name, level_str in self.logger_levels.items():
                logging.getLogger(name).setLevel(
                    getattr(logging, level_str, logging.WARNING)
                )
        else:
            root.setLevel(logging.WARNING)


# Application-wide singleton — import and use directly:
#   from finch.config import app_settings
app_settings = Settings()