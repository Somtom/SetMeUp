import os
import logging
import hashlib
import subprocess
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def checksum_from_file(file_path: str) -> str:
    # Read file content
    try:
        with open(file_path, 'r') as file:
            content = file.read()
    except FileNotFoundError:
        raise Exception(f"File '{file_path}' not found")

    # Generate SHA256 checksum
    sha256 = hashlib.sha256(content.encode('utf-8')).hexdigest()
    return sha256


def checksum_from_string(string: str) -> str:
    return hashlib.sha256(string.encode('utf-8')).hexdigest()


def check_if_step_ran(validation_check_cmd: Optional[str]) -> bool:
    completed = False
    if validation_check_cmd:
        completed = subprocess.call(validation_check_cmd, shell=True) == 0
    return completed


def is_file(string: Optional[str] = None):
    return string is not None and os.path.isfile(os.path.join(string))


def get_file_content_or_command(script) -> str:
    script_content = ""
    if is_file(script):
        # If it's a file, read its content
        try:
            with open(script, 'r') as file:
                script_content = file.read()
        except FileNotFoundError:
            raise Exception(f"Script file '{script}' not found")
    else:
        # If it's not a file, use the script string directly
        script_content = script

    return script_content
