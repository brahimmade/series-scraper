from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer

from plex.model import PlexEpisode
from seriesscraper.config.config import Config


class Plex:
    def __init__(self) -> None:
        super().__init__()
        config = Config.instance()
        self.__connect_to_plex(config)
        self.__load_variables_from(config)

    def __connect_to_plex(self, config) -> None:
        plex_username, plex_password, plex_server = config.get_plex_credentials()
        account = MyPlexAccount(plex_username, plex_password)
        self.plex: PlexServer = account.resource(plex_server).connect()

    def __load_variables_from(self, config):
        self.tv_library_name = config.get_plex_tv_library()

    def get_existing_episodes_of(self, tv_series: str) -> [PlexEpisode]:
        """
        Get existing episodes of a tv series.
        :param tv_series: Name of the tv series.
        :return: List of existing episodes.
        """
        tv_library = self.plex.library.section(self.tv_library_name)
        series = tv_library.search(title=tv_series, libtype='show').pop()
        return series.episodes()
