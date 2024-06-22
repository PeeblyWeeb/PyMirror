import shutil
import argparse
import tomllib
import time
import logging
import sys

from pathlib import Path
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

if not Path("mirror_config.toml").exists():
    default_config: tuple[str] = (
        "# The path to the folder that includes all of your subfolders.",
        "ROOT_FOLDER_PATH = \"\"\n",
        "# By default folders starting with '.' in the root folder are excluded, create exclusing by passing in folder names here.",
        "EXCLUSION_OVERRIDES = [\".Single\"]\n",
        "# How long the program stays open (IN SECONDS) before it closes the terminal, set to -1 to never close unless closed by you.",
        "CLOSE_DELAY = 0\n",
        "# Wether to include the original file names in the mirror folder, does not work when using '--randomize'",
        "PRESERVE_FILE_NAMES = true\n",
        "# Where should the .Mirror folder be placed and read from? Set to '.' for root folder.",
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

ROOT_FOLDER_PATH: Path = Path(config.get("ROOT_FOLDER_PATH"))
EXCLUSION_OVERRIDES: list[str] = config.get("EXCLUSION_OVERRIDES")
CLOSE_DELAY: int = config.get("CLOSE_DELAY")
PRESERVE_FILE_NAMES: bool = config.get("PRESERVE_FILE_NAMES")
MIRROR_FOLDER_PATH: Path = ROOT_FOLDER_PATH if config.get("MIRROR_FOLDER_PATH") == "." else Path(config.get("MIRROR_FOLDER_PATH"))
PATH_SEPARATOR: str = config.get("PATH_SEPARATOR")

REQUIRED_SETTINGS = ["ROOT_FOLDER_PATH", "EXCLUSION_OVERRIDES", "CLOSE_DELAY", "PRESERVE_FILE_NAMES", "MIRROR_FOLDER_PATH", "PATH_SEPARATOR"]
REAL_MIRROR_FOLDER = MIRROR_FOLDER_PATH / ".Mirror"
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

if not ROOT_FOLDER_PATH.exists():
    logger.critical("Root folder path doesn't actually exist, double check your spelling.")
    exit()
if not REAL_MIRROR_FOLDER.exists():
    logger.info(f"Existing .Mirror folder not found in '{MIRROR_FOLDER_PATH}', creating one now!")
    REAL_MIRROR_FOLDER.touch()

logger.info(f"Using folder '{ROOT_FOLDER_PATH}' as root folder")
logger.info(f"Using folder '{REAL_MIRROR_FOLDER}' as mirror folder")

logger.info("Erasing previous mirror")
for fsobj in REAL_MIRROR_FOLDER.iterdir():
    logger.debug(f"Deleting file '{fsobj.name}' from previous mirror..")
    fsobj.unlink()
    
logger.info("Updating mirror")
def mirror_folder(path: Path):
    for i,fsobj in enumerate(path.iterdir()):
        if fsobj.name.startswith(".") and fsobj.name not in EXCLUSION_OVERRIDES:
            logger.debug(f"Skipping folder '{fsobj.name}' because it starts with '.' and it is not added as an exclusion override.")
            continue
        if not fsobj.is_file():
            mirror_folder(fsobj)
            continue
        if fsobj.suffix == ".ini":
            logger.debug(f"Skipping file '{fsobj.name}' because it uses the file extension '.ini'.")
            continue

        relative_fsobj = fsobj.relative_to(ROOT_FOLDER_PATH)
        file_name = f"{relative_fsobj.as_posix().replace("/", PATH_SEPARATOR)}" \
                    if PRESERVE_FILE_NAMES else \
                    f"{relative_fsobj.parent.as_posix().replace("/", PATH_SEPARATOR)}-{i}{relative_fsobj.suffix}"
        
        logger.debug(f"Copying file '{fsobj.name}' to '{REAL_MIRROR_FOLDER / file_name}' ..")
        shutil.copyfile(str(fsobj), REAL_MIRROR_FOLDER / file_name)
mirror_folder(ROOT_FOLDER_PATH)

logger.info("Mirror updated! If something doesn't look right, double check for warnings above!")
logger.info("Still can't find your problem? Try running with '-v' or '--verbose'")

while CLOSE_DELAY == -1:
    pass
for i in range(CLOSE_DELAY):
    logger.info(CLOSE_MESSAGE.format(CLOSE_DELAY - i) + "." * i)
    time.sleep(CLOSE_DELAY / CLOSE_DELAY)
