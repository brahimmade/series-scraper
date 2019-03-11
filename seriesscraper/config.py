import logging
import sys
from pathlib import Path

__config_file = Path(__file__).parents[1] / 'config.yaml'  # root dir of project


def load_config(config_file: str = __config_file) -> dict:
    import yaml

    config_file_path = Path(config_file)
    if not config_file_path.is_file() or config_file_path.stat().st_size == 0:
        logging.error('Please provide a configuration file before starting the crawler.')
        sys.exit(0)

    with open(config_file, 'r') as file_handle:
        content = yaml.load(file_handle)  # throws YAMLError
        return content
