import logging
import sys

__config_file = '..\\config.yaml'


def load_config(file: str = __config_file) -> dict:
    import yaml, os
    file_dir = os.path.dirname(__file__)
    if not os.path.isfile(os.path.join(file_dir, file)) or os.path.getsize(os.path.join(file_dir, file)) == 0:
        logging.error('Please provide a configuration file before starting the crawler.')
        sys.exit(0)

    with open(os.path.join(file_dir, file), 'r') as file_handle:
        content = yaml.load(file_handle)  # throws YAMLError
        return content
