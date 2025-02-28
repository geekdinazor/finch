import json
import os
from pathlib import Path
from typing import List


def get_config_path():
    return os.path.join(Path.home(), ".config/finch")


def create_config_files_if_not_exist():
    config_path = get_config_path()
    os.makedirs(config_path, exist_ok=True)
    Path(os.path.join(config_path, 'credentials.json')).touch()
    Path(os.path.join(config_path, 'settings.json')).touch()


def get_credentials_path():
    return os.path.join(get_config_path(), 'credentials.json')


def get_settings_path():
    return os.path.join(get_config_path(), 'settings.json')

# Credentials Operations

def get_credentials() -> List[dict]:
    with open(get_credentials_path(), 'r') as file:
        return json.load(file)

def write_credentials(credentials: List[dict]) -> None:
    with open(get_credentials_path(), 'w') as file:
        file.write(json.dumps(credentials, indent=4))

def get_credential(credential_name: str) -> dict:
    return list(filter(lambda credential: credential['name'] == credential_name, get_credentials())).pop()

def get_credentials_names() -> List[str]:
    return [credential['name'] for credential in get_credentials()]

def get_credential_by_name(name: str) -> dict:
    credentials = get_credentials()
    return next((cred for cred in credentials if cred['name'] == name), None)