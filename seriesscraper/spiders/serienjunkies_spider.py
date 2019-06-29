import re
from enum import Enum
from typing import Match

import scrapy
from scrapy import signals, Request
from scrapy.http.response import Response

from plex.model import PlexEpisode
# TODO: Refactor code to use Scrapy Item Loaders
#       See https://docs.scrapy.org/en/latest/topics/loaders.html for further details.
from plex.plex import Plex
from seriesscraper.config.config import Config
from seriesscraper.config.model import TvShowConfig, LanguageConfig
from seriesscraper.items import EpisodeItem


class MetaItem(Enum):
    TV_SHOW = 1
    EXISTING_EPISODES = 2


SEASON_EPISODE_PATTERN = 'S(\\d{2})E(\\d{2})'


class SerienjunkiesSpider(scrapy.Spider):
    name = 'serienjunkies_spider'
    allowed_domains = ['serienjunkies.org']
    start_urls = ['http://serienjunkies.org/serien/?cat=0&showall']  # crawler entry point

    # region spider initialization
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

    # endregion

    # region initial parse
    def parse(self, response: Response):
        for tv_show in self.config.get_tv_shows():
            tv_show_link = self.__crawl_tv_show_link_of(tv_show, response)
            existing_episodes = self.__get_existing_episodes_as_episode_items_of(tv_show)
            yield self.__next_request(link=tv_show_link,
                                      callback=self.parse_tv_show_season,
                                      tv_show=tv_show,
                                      existing_episodes=existing_episodes)

    def __crawl_tv_show_link_of(self, tv_show: TvShowConfig, response: Response):
        xpath_selector = '//li[contains(@class, "cat-item")]//a[text()="{}"]/@href'.format(tv_show.name)
        return response.xpath(xpath_selector).get()

    def __get_existing_episodes_as_episode_items_of(self, tv_show: TvShowConfig):
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

    # endregion

    # region tv show season parse
    def parse_tv_show_season(self, response: Response):
        tv_show, existing_episodes, latest_episode = self.__extract_meta_info_from(response)

        crawl_results = self.__crawl_release_title_download_links(response)
        downloadable_episode_items = self.__map_crawl_results_to_episode_items(tv_show, crawl_results)

        # TODO: Match complete seasons from crawl results against season pattern (S\\d{2}) if results are empty when
        #  matching against season episode pattern

        only_latest_episodes = self.config.get_only_latest_episodes()
        if only_latest_episodes:
            for latest_episode in self.__latest_episodes_of(downloadable_episode_items, latest_episode):
                yield latest_episode
        else:
            for not_yet_existing_episode in self.__not_yet_existing_episodes_of(downloadable_episode_items,
                                                                                existing_episodes):
                yield not_yet_existing_episode

        yield self.__crawl_next_page(response, tv_show, existing_episodes)

    def __crawl_release_title_download_links(self, response: Response) -> [(str, str)]:
        language = self.config.get_language()
        hoster = self.config.get_serienjunkies_hoster()

        episode_p_tags = self.__crawl_episode_p_tags_by_language(response, language)
        crawl_results = self.__crawl_download_links_of(episode_p_tags, hoster)

        return crawl_results

    def __crawl_episode_p_tags_by_language(self, response: Response, language: LanguageConfig):
        episode_p_tag_xpath_query = '''
        //p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and 
        (
         ./strong/text()[contains(., \'1080p\') and contains(., \'WEB-DL\')] or
         ./strong/text()[contains(., \'1080p\')] or
         ./strong/text()[contains(., \'720p\') and contains(., \'WEB-DL\')] or
         ./strong/text()[contains(., \'720p\')]
        )] ''' \
            if language == LanguageConfig.ENGLISH else \
            '''
        //p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and 
        (
         ./strong/text()[contains(., \'1080p\') and contains(., \'WEB-DL\') and contains(translate(., 'GERMAN', 'german'), 'german')] or
         ./strong/text()[contains(., \'1080p\') and contains(translate(., 'GERMAN', 'german'), 'german')] or
         ./strong/text()[contains(., \'720p\') and contains(., \'WEB-DL\') and contains(translate(., 'GERMAN', 'german'), 'german')] or
         ./strong/text()[contains(., \'720p\') and contains(translate(., 'GERMAN', 'german'), 'german')]
        )]'''
        return response.xpath(episode_p_tag_xpath_query)

    def __crawl_download_links_of(self, episode_p_tags, hoster: str) -> [(str, str)]:
        def extract_release_title(a_tag):
            return a_tag.xpath('preceding-sibling::strong[not(text()=\'Download:\')]/text()').get()

        def extract_download_link(a_tag):
            return a_tag.css('::attr(href)').get()

        def extract_a_tags(p_tags, hoster):
            return p_tags.xpath('child::a[./following-sibling::text()[1][contains(., \'{0}\')]]'.format(hoster))

        release_titles_and_download_links = \
            [(extract_release_title(a_tag), extract_download_link(a_tag))
             for a_tag in extract_a_tags(episode_p_tags, hoster)]

        release_titles_and_download_links.reverse()
        return release_titles_and_download_links

    def __latest_episodes_of(self, episode_items: [EpisodeItem], latest_episode: EpisodeItem):
        for episode_item in episode_items:
            yield episode_item if episode_item > latest_episode else None

    def __not_yet_existing_episodes_of(self, episode_items: [EpisodeItem], existing_episodes: [EpisodeItem]):
        for episode_item in episode_items:
            yield episode_item if episode_item not in existing_episodes else None

    def __map_crawl_results_to_episode_items(self,
                                             tv_show: TvShowConfig,
                                             crawl_results: [(str, str)]) -> [EpisodeItem]:
        def get_season_episode_match(release_title: str) -> Match:
            return re.search(SEASON_EPISODE_PATTERN, release_title)

        def extract_season_episode_info_from(season_episode_match: Match):
            season_number = int(season_episode_match.group(1))
            episode_number = int(season_episode_match.group(2))
            season_episode_string = '{}{}'.format(season_number, episode_number)
            return season_number, episode_number, season_episode_string

        mapped_episode_items = {}
        for release_title, download_link in crawl_results:
            season_episode_match = get_season_episode_match(release_title)
            if not season_episode_match:
                continue

            season_number, episode_number, season_episode_string = \
                extract_season_episode_info_from(season_episode_match)

            if season_episode_string not in mapped_episode_items:
                new_episode_item = EpisodeItem(
                    tv_show_name=tv_show.name,
                    season_number=season_number,
                    episode_number=episode_number,
                    release_downloadlink_tuples=[]
                )
                mapped_episode_items[season_episode_string] = new_episode_item

            # append crawl result to episode item
            mapped_episode_items[season_episode_string]['release_downloadlink_tuples'].append(
                (release_title, download_link))

        return mapped_episode_items.values()

    def __crawl_next_page(self, response: Response, tv_show: TvShowConfig, existing_episodes: [EpisodeItem]):
        next_page_link = self.__crawl_next_page_link(response)
        return self.__next_request(link=next_page_link,
                                   callback=self.parse_tv_show_season,
                                   tv_show=tv_show,
                                   existing_episodes=existing_episodes) \
            if next_page_link is not None \
            else None

    def __crawl_next_page_link(self, response: Response):
        return response.xpath('//a[@class="next"]/@href').get()
    # endregion

    # region utility
    def __next_request(self, link: str,
                       callback,
                       tv_show: TvShowConfig,
                       existing_episodes: [EpisodeItem] = None) -> Request:
        request = scrapy.Request(link, callback=callback)
        request.meta[MetaItem.TV_SHOW] = tv_show
        request.meta[MetaItem.EXISTING_EPISODES] = existing_episodes
        return request

    def __extract_meta_info_from(self, response: Response) -> (TvShowConfig, [EpisodeItem], EpisodeItem):
        tv_show = response.meta[MetaItem.TV_SHOW]
        existing_episodes = response.meta[MetaItem.EXISTING_EPISODES]
        latest_episode = existing_episodes[-1] if existing_episodes else None

        return tv_show, existing_episodes, latest_episode
    # endregion
