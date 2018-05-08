import re

import scrapy
from scrapy import signals

from seriesscraper.config import load_config
from seriesscraper.items import SeriesEpisodeDownloadItem

# TODO: Optimize season and episode search limit by fetching the latest episode from some kind of series guide website
# Some arbitrary limit has to do for now. Will be a problem if a series has more than 15 seasons or more than 40 episodes.
SEASON_SEARCH_LIMIT = 15
EPISODE_SEARCH_LIMIT = 40


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
        from plexapi.myplex import MyPlexAccount
        self.config = load_config()

        plex_username = self.config['plex']['username']
        plex_password = self.config['plex']['password']
        plex_server = self.config['plex']['server_name']

        account = MyPlexAccount(plex_username, plex_password)
        self.plex = account.resource(plex_server).connect()

    def parse(self, response):
        link = 'http://serienjunkies.org/serie/{}'

        for series in self.config['series']:
            # get info of latest episode from plex
            season_number, episode_number = get_latest_episode(self.plex, series_name=series['name'])
            # extract next link from config
            next_link = link.format(series['link_suffix'])

            request = scrapy.Request(next_link, callback=self.parse_series_landing_page)  # build next request
            # add season number and episode number to request for next callback
            request.meta['series'] = series
            request.meta['season_number'] = season_number
            request.meta['episode_number'] = episode_number
            yield request

    def parse_series_landing_page(self, response):
        # get season number and episode number from response
        series = response.meta['series']
        season_number = response.meta['season_number']
        episode_number = response.meta['episode_number']

        # get a-tags resembling the season links
        nodes = [(a_node.css('::text').extract()[0], a_node.css('::attr(href)').extract()[0])
                 for a_node in response.css('#scb a')]

        # filter english seasons
        filtered_sorted_nodes = [(label, link) for (label, link) in nodes if re.search('Season', label)]

        for i in range(season_number, 15):
            season = next(((label, link) for (label, link) in filtered_sorted_nodes if
                           re.search('(\s{0}\s)|(\s{0}-{1}\s)|(\s{2}-{0}\s)'.format(i, i + 1, i - 1), label)), None)
            if season is None:
                continue

            season_link = season[1]
            request = scrapy.Request(season_link, callback=self.parse_series_season)
            # add season number and episode number to request for next callback
            request.meta['series'] = series
            request.meta['season_number'] = season_number
            request.meta['episode_number'] = episode_number
            yield request

    def parse_series_season(self, response):
        series = response.meta['series']
        season_number = response.meta['season_number']
        episode_number = response.meta['episode_number']

        hoster = 'share-online'

        # get p-tags resembling the correct episodes and filter them by episode and quality
        fullhd_webdl_nodes = response.xpath(
            '//p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and ./strong/text()[contains(., \'1080p\') and contains(., \'WEB-DL\')]]')
        fullhd_nodes = response.xpath(
            '//p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and ./strong/text()[contains(., \'1080p\')]]')
        hdready_webdl_nodes = response.xpath(
            '//p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and ./strong/text()[contains(., \'720p\') and contains(., \'WEB-DL\')]]')
        hdready_nodes = response.xpath(
            '//p[position()>2 and not(@class) and not(contains(., \'Dauer\')) and ./strong/text()[contains(., \'720p\')]]')

        hd_nodes = [fullhd_webdl_nodes, fullhd_nodes, hdready_webdl_nodes, hdready_nodes]

        next_episode = episode_number + 1
        for nodes in hd_nodes:
            for i in range(next_episode, EPISODE_SEARCH_LIMIT):
                # get a-tags resembling the download links
                a_nodes = [(a_node.css('::text').extract()[0], a_node.css('::attr(href)').extract()[0])
                           for a_node in
                           nodes.xpath(
                               'child::a[./following-sibling::text()[contains(., \'{0}\')] and ./preceding-sibling::*[contains(., \'S{1:02d}E{2:02d}\')]]'.format(
                                   hoster, season_number, i))]

                # if we couldn't find any download links for the current quality,
                # break from the current episode loop and continue the nodes loop
                if not a_nodes:
                    break
                # else save the latest found episode and yield the result
                else:
                    next_episode = i + 1
                    for a_node in a_nodes:  # we loop here just in case serienjunkies has multiple releases with the same quality
                        yield SeriesEpisodeDownloadItem(series_name=series['name'], season_number=season_number,
                                                        episode_number=i, download_link=a_node[1])

            # if the next episode is above our maximum search limit, we have found every episode already, so we don't have to
            # continue our search down the quality list
            if next_episode == EPISODE_SEARCH_LIMIT + 1:
                break


def get_latest_episode(plex, series_name: str) -> (int, int):
    def split_season_episode(season_episode: str) -> (str, str):
        return int(season_episode[1:-3]), int(season_episode[4:])

    series_episodes = plex.library.section('TV-Serien').get(series_name).episodes()
    latest_episode = series_episodes[-1]
    return split_season_episode(latest_episode.seasonEpisode)
