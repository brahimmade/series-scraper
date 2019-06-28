import logging
import sys
from pathlib import Path

from seriesscraper.config.model import TvShowConfigEntry
from seriesscraper.singleton import Singleton


@Singleton
class Config:
    __config_file = Path(__file__).parents[2] / 'config.yaml'  # root dir of project

    def __init__(self) -> None:
        self.__config = self.__load_config()

    def __load_config(self) -> dict:
        import yaml

        config_file_path = Path(self.__config_file)
        if not config_file_path.is_file() or config_file_path.stat().st_size == 0:
            logging.error('Please provide a configuration file before starting the crawler.')
            sys.exit(0)

        with open(self.__config_file, 'r') as file_handle:
            content = yaml.load(file_handle)  # throws YAMLError
            return content

    def get_language(self) -> str:
        return self.__config['general']['language']

    def get_only_latest_episodes(self) -> bool:
        return self.__config['general']['only_latest_episodes']

    def get_tv_shows(self) -> [TvShowConfigEntry]:
        return [TvShowConfigEntry(name=tv_show['name'])
                for tv_show in self.__config['tv_shows']]

    def get_plex_credentials(self) -> (str, str, str):
        return self.__config['plex']['username'], self.__config['plex']['password'], self.__config['plex'][
            'server_name']

    def get_plex_tv_library(self) -> str:
        return self.__config['plex']['tv_library_name']

    def get_serienjunkies_hoster(self) -> str:
        return self.__config['serienjunkies']['hoster']

    def get_jd_credentials(self) -> (str, str, str):
        return self.__config['item_pipelines']['myjdownloader']['email'], \
               self.__config['item_pipelines']['myjdownloader']['password'], \
               self.__config['item_pipelines']['myjdownloader']['device_name']

    def get_jd_autostart_downloads(self) -> bool:
        return self.__config['item_pipelines']['myjdownloader']['autostart_downloads']

    def get_jd_tv_show_dir(self) -> str:
        return self.__config['item_pipelines']['myjdownloader']['tv_shows_dir']
