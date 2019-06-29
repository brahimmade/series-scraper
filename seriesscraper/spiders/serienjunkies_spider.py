import re
from enum import Enum

import scrapy
from scrapy import signals, Request
from scrapy.http.response import Response

from plex.model import PlexEpisode
# TODO: Refactor code to use Scrapy Item Loaders
#       See https://docs.scrapy.org/en/latest/topics/loaders.html for further details.
from plex.plex import Plex
from seriesscraper.config.config import Config
from seriesscraper.config.model import TvShowConfigEntry
from seriesscraper.items import EpisodeItem


class MetaItem(Enum):
    TV_SHOW = 1
    EXISTING_EPISODES = 2


class SerienjunkiesSpider(scrapy.Spider):
    name = 'serienjunkies_spider'
    allowed_domains = ['serienjunkies.org']
    start_urls = ['http://serienjunkies.org/serien/?cat=0&showall']  # crawler entry point

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(SerienjunkiesSpider, cls).from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_opened, signal=signals.spider_opened)
        return spider

    def spider_opened(self, spider):
        self.__load_config_into_context(spider)
        self.__load_plex_into_context(spider)
        self.__load_internationalization_into_context(spider)

    def __load_config_into_context(self, spider) -> None:
        spider.config = Config.instance()

    def __load_plex_into_context(self, spider) -> None:
        spider.plex = Plex()

    def __load_internationalization_into_context(self, spider) -> None:
        # load i18 TODO: Refactor internationalization
        crawl_language = Config.instance().get_language()
        spider.season_regex_i18 = 'Season (\\d+)' if crawl_language == 'english' else 'Staffel (\\d+)'

    def parse(self, response: Response):
        for tv_show in self.config.get_tv_shows():
            tv_show_link = self.__crawl_tv_show_link_of(tv_show, response)
            yield self.__next_request(link=tv_show_link,
                                      callback=self.parse_tv_show_landing_page,
                                      tv_show=tv_show)

    def __crawl_tv_show_link_of(self, tv_show: TvShowConfigEntry, response: Response):
        xpath_selector = '//li[contains(@class, "cat-item")]//a[text()="{}"]/@href'.format(tv_show.name)
        return response.xpath(xpath_selector).get()

    def parse_tv_show_landing_page(self, response):
        # get tv show title and existing episodes from response
        tv_show: TvShowConfigEntry = response.meta[MetaItem.TV_SHOW]
        existing_episodes = self.__get_existing_episodes_as_episode_items_of(tv_show)
        latest_episode = existing_episodes[-1]

        # retrieve season links from a-tags on the page
        season_links = [(a_node.css('::text').extract()[0], a_node.css('::attr(href)').extract()[0])
                        for a_node in response.css('#scb a')]

        # filter links by language and extract season number from label
        numbered_season_links_by_language = []
        for label, link in season_links:
            match = re.search(self.season_regex_i18, label)
            if match:
                numbered_season_links_by_language.append((int(match.group(1)), link))

        # build next requests
        for season_number, season_link in numbered_season_links_by_language:
            # skip seasons that are already present in library if only latest episodes is True
            only_latest_episodes = self.config.get_only_latest_episodes()
            if only_latest_episodes and season_number < latest_episode['season_number'] - 1:
                continue

            yield self.__next_request(link=season_link,
                                      callback=self.parse_tv_show_season,
                                      tv_show=tv_show,
                                      existing_episodes=existing_episodes)

    def __get_existing_episodes_as_episode_items_of(self, tv_show: TvShowConfigEntry):
        return self.__map_plex_episodes_to_episode_item(
            self.plex.get_existing_episodes_of(tv_show.name)
        )

    def __map_plex_episodes_to_episode_item(self, plex_episodes: [PlexEpisode]) -> [EpisodeItem]:
        def extract_season_number(season_episode: str) -> int:
            return int(season_episode[1:-3])

        def extract_episode_number(season_episode: str) -> int:
            return int(season_episode[4:])

        return [
            EpisodeItem(
                tv_show_name=plex_episode.grandparentTitle,
                season_number=extract_season_number(plex_episode.seasonEpisode),
                episode_number=extract_episode_number(plex_episode.seasonEpisode),
                release_downloadlink_tuples=[]
            ) for plex_episode in plex_episodes
        ]

    def parse_tv_show_season(self, response):
        tv_show: TvShowConfigEntry = response.meta[MetaItem.TV_SHOW]
        existing_episodes: [EpisodeItem] = response.meta[MetaItem.EXISTING_EPISODES]
        latest_episode = existing_episodes[-1]

        # retrieve p-tag container of correct episodes and filter them by episode and quality
        hd_nodes = response.xpath('''
        //p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and 
        (
         ./strong/text()[contains(., \'1080p\') and contains(., \'WEB-DL\')] or
         ./strong/text()[contains(., \'1080p\')] or
         ./strong/text()[contains(., \'720p\') and contains(., \'WEB-DL\')] or
         ./strong/text()[contains(., \'720p\')]
        )]
        ''')

        # retrieve download links for configured hoster
        hoster = self.config.get_serienjunkies_hoster()
        crawl_results = [(node.xpath('preceding-sibling::strong[not(text()=\'Download:\')]/text()')
                          .extract()[0],  # release title
                          node.css('::attr(href)').extract()[0])  # download link
                         for node in hd_nodes.xpath('child::a[./following-sibling::text()[1][contains(., \'{0}\')]]'
                                                    .format(hoster))]

        # this is necessary because episodes are sorted by quality in ascending order but we want the best quality at
        # the top of the list
        crawl_results.reverse()

        # map crawl results to EpisodeItem
        downloadable_episodes = {}  # dict for already mapped episodes
        for release_title, download_link in crawl_results:
            # match release title against season episode pattern
            match = re.search('S(\\d{2})E(\\d{2})', release_title)
            if not match:
                continue  # release is not a season episode, skip result

            # extract season number and episode number from release title
            season_number = int(match.group(1))
            episode_number = int(match.group(2))
            # build season episode string that will be used as key in result dict
            season_episode = '{}{}'.format(season_number, episode_number)

            # get existing episode item from result dict
            downloadable_episode = downloadable_episodes.get(season_episode)
            # if it doesn't exist yet, create new episode item if it doesn't exist yet and add it to result dict
            if not downloadable_episode:
                downloadable_episode = EpisodeItem(tv_show_name=tv_show.name, season_number=season_number,
                                                   episode_number=episode_number, release_downloadlink_tuples=[])
                downloadable_episodes[season_episode] = downloadable_episode

            # append crawl result to episode item
            downloadable_episode['release_downloadlink_tuples'].append((release_title, download_link))

        # TODO: Match complete seasons from crawl results against season pattern (S\\d{2}) if results are empty when
        #  matching against season episode pattern

        # yield results if:
        # - the user wants to crawl every missing episode AND it's not in his library yet
        # - the user only wants to crawl the latest episode AND it's newer than the latest existing episode
        #   in his library
        for downloadable_episode in downloadable_episodes.values():
            only_latest_episodes = self.config.get_only_latest_episodes()
            if only_latest_episodes and downloadable_episode > latest_episode \
                    or not only_latest_episodes and downloadable_episode not in existing_episodes:
                yield downloadable_episode

    def __next_request(self, link: str,
                       callback,
                       tv_show: TvShowConfigEntry,
                       existing_episodes: [EpisodeItem] = None) -> Request:
        request = scrapy.Request(link, callback=callback)
        request.meta[MetaItem.TV_SHOW] = tv_show
        request.meta[MetaItem.EXISTING_EPISODES] = existing_episodes
        return request
