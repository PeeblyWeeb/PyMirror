import os
import shutil
import argparse
import tomllib
import time
import re
import logging
import sys

from typing import ClassVar
from string import ascii_letters
from random import choices


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(levelname)s: %(message)s"

    FORMATS: ClassVar = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

if not os.path.exists("mirror_config.toml"):
    default_config: tuple[str] = (
        "# The path to the folder that includes all of your image pair subfolders.",
        "ROOT_FOLDER_PATH = \"\"\n",
        "# By default folders starting with '.' in the root folder are excluded, create exclusing by passing in folder names here.",
        "EXCLUSION_OVERRIDES = [\".Single\"]\n",
        "# How long the program stays open (IN SECONDS) before it closes the terminal, set to -1 to never close unless closed by you.",
        "CLOSE_DELAY = 0\n",
        "# Wether to include the original file names in the mirror folder, does not work when using '--randomize'",
        "PRESERVE_FILE_NAMES = true\n",
        "# Where should the .Mirror folder be placed and read from? Set to '.' for root folder.",
        "# PLEASE BE CAREFUL WHEN USING THIS SETTING!",
        "# THE MIRROR FOLDER WILL BE DESTROYED ON EVERY RUN OF THIS SCRIPT, DO NOT SET IT TO AN IMPORTANT FOLDER!",
        "MIRROR_FOLDER_PATH = \".\"\n",
        "# Folder separator for mirrored files, so if a file was located at '<root>/a/b/file.txt' it would be 'a<PATH SEPARATOR>b<PATH SEPARATOR>file.txt' in the mirror folder.",
        "PATH_SEPARATOR = \"#,\""
    )
    with open("mirror_config.toml", "wb") as f:
        f.write("\n".join(default_config).encode("utf-8"))

with open("mirror_config.toml") as f:
    config = tomllib.loads(f.read())


parser = argparse.ArgumentParser()
parser.add_argument("-r", "--randomize", action="store_true")
parser.add_argument("-v", "--verbose", action="store_true")

args = parser.parse_args()

ROOT_FOLDER_PATH: str = config.get("ROOT_FOLDER_PATH")
EXCLUSION_OVERRIDES: list[str] = config.get("EXCLUSION_OVERRIDES")
CLOSE_DELAY: int = config.get("CLOSE_DELAY")
PRESERVE_FILE_NAMES: bool = config.get("PRESERVE_FILE_NAMES")
MIRROR_FOLDER_PATH: str = config.get("MIRROR_FOLDER_PATH")
PATH_SEPARATOR: str = config.get("PATH_SEPARATOR")

REQUIRED_SETTINGS = ["ROOT_FOLDER_PATH", "EXCLUSION_OVERRIDES", "CLOSE_DELAY", "PRESERVE_FILE_NAMES", "MIRROR_FOLDER_PATH", "PATH_SEPARATOR"]
FILE_EXTENSION_REGEX: str = r"^(.*)\.(.*)$"
CLOSE_MESSAGE = "This window will close in {0} seconds."
RANDOMIZE = args.randomize
VERBOSE = args.verbose

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO if not VERBOSE else logging.DEBUG)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

missing_setting_errors = [
    f"{setting} not defined in configuration file or has useless value. Find configuration in the same directory as this script"
    for setting in REQUIRED_SETTINGS if config.get(setting) == "" or config.get(setting) is None
]
if missing_setting_errors:
    logger.critical("\n".join(missing_setting_errors) + "\n")
    logger.critical("Don't see some of those setting in your config file? Delete it and allow it to regenerate.")
    exit()

ROOT_FOLDER_PATH += "/" if not ROOT_FOLDER_PATH.endswith("/") else ""
logger.info(f"Using folder '{ROOT_FOLDER_PATH}' as root folder")

MIRROR_FOLDER_PATH = ROOT_FOLDER_PATH if MIRROR_FOLDER_PATH == "." else MIRROR_FOLDER_PATH
MIRROR_FOLDER_PATH += "/" if not MIRROR_FOLDER_PATH.endswith("/") else ""
REAL_MIRROR_FOLDER = MIRROR_FOLDER_PATH + ".Mirror/"
logger.info(f"Using folder '{REAL_MIRROR_FOLDER}' as mirror folder")

if not os.path.exists(ROOT_FOLDER_PATH):
    logger.critical("Root folder path doesn't actually exist, double check your spelling.")
    exit()
if not os.path.exists(REAL_MIRROR_FOLDER):
    logger.info(f"Existing .Mirror folder not found in '{MIRROR_FOLDER_PATH}', creating one now!")
    os.mkdir(REAL_MIRROR_FOLDER)


def MirrorFiles(path="unknown"):
    logger.debug(f"Mirroring files & folders from '{path}'")
    try:
        for i,file_or_folder in enumerate(os.listdir(ROOT_FOLDER_PATH + path)):
            # Check if the current file / folder in iteration is a folder or not, if it's a folder, recursively call this function and continue.
            if not os.path.isfile(ROOT_FOLDER_PATH + f"{path}/{file_or_folder}"):
                MirrorFiles(f"{path}/{file_or_folder}")
                continue
            
            # Find the current file extension, if there is none warn the user and default to .unknown
            match = re.match(FILE_EXTENSION_REGEX, file_or_folder, flags=re.IGNORECASE)
            if match is None:
                logger.warning(f"No file name extension found on file '{file_or_folder}' !!! (Defaulting to .unknown)")
                file_name = file_or_folder
                extension = "unknown"
            else:
                file_name = match[1]
                extension = match[2]

            # Construct the name of the file based on its path and how many other files have the same path
            FILE_NAME = f"{PATH_SEPARATOR.join(path.split('/'))}.{file_name if PRESERVE_FILE_NAMES else i}.{extension}" if not RANDOMIZE else f"{''.join(choices(ascii_letters, k=20))}.{extension}"
            logger.debug(f"Copying file '{file_or_folder}' to '{REAL_MIRROR_FOLDER}{FILE_NAME}' ..")
            try:
                shutil.copyfile(ROOT_FOLDER_PATH + f"{path}/{file_or_folder}", REAL_MIRROR_FOLDER + FILE_NAME)
            except OSError as e:
                logger.error(f"Skipping file {ROOT_FOLDER_PATH + f"{path}/{file_or_folder}"} because the system threw a permission error! ({e})")
                continue
    except OSError as e:
        logger.error(f"Skipping folder '{path}' because the system threw a permission error! ({e})")


logger.info("Erasing previous mirror")
for image in os.listdir(REAL_MIRROR_FOLDER):
    logger.debug(f"Deleting image '{REAL_MIRROR_FOLDER + image}' from previous mirror..")
    os.remove(REAL_MIRROR_FOLDER + image)


logger.info("Updating mirror")
for folder_name in os.listdir(ROOT_FOLDER_PATH):
    if os.path.isfile(ROOT_FOLDER_PATH + folder_name):
        logger.warning(f"Ignoring file '{folder_name}' because it is not a folder, only folders should be in the root folder.")
        continue
    if folder_name.startswith(".") and folder_name not in EXCLUSION_OVERRIDES:
        if VERBOSE:
            logger.debug(f"Skipping folder '{folder_name}' because it starts with '.' and it is not added as an exclusion override.")
        continue

    MirrorFiles(folder_name)
logger.info("Mirror updated! If something doesn't look right, double check for warnings above!\n")

if CLOSE_DELAY == -1:
    logger.warning("This window will never close, feel free to close it at your leisure.")
    while True:
        pass
if CLOSE_DELAY == 0:
    exit()
for i in range(CLOSE_DELAY):
    logger.info(CLOSE_MESSAGE.format(CLOSE_DELAY - i) + "." * i)
    time.sleep(CLOSE_DELAY / CLOSE_DELAY)