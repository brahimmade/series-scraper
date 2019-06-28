from dataclasses import asdict

from myjdapi import myjdapi

from seriesscraper.config.config import Config
from seriesscraper.jdownloader.jdlink import JdLink


class Jd:
    def __init__(self) -> None:
        super().__init__()
        config = Config.instance()
        self.__connect_to_jd(config)

    def __connect_to_jd(self, config):
        email, password, device = config.get_jd_credentials()
        jd = myjdapi.Myjdapi()
        jd.connect(email, password)
        self.jd_device = jd.get_device(device)

    def add_link(self, jd_link: JdLink):
        self.jd_device.linkgrabber.add_links([asdict(jd_link)])
