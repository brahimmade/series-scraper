import re

import scrapy
from scrapy import signals

from seriesscraper.config import load_config
from seriesscraper.items import SeriesEpisodeItem


# TODO: Refactor code to use Scrapy Item Loaders
#       See https://docs.scrapy.org/en/latest/topics/loaders.html for further details.


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
        spider.config = load_config()

        # initialize plex connection
        plex_username = spider.config['plex']['username']
        plex_password = spider.config['plex']['password']
        plex_server = spider.config['plex']['server_name']

        account = MyPlexAccount(plex_username, plex_password)
        spider.plex = account.resource(plex_server).connect()

        # load i18 TODO: Refactor internationalization
        crawl_language = spider.config['general']['language']
        spider.season_regex_i18 = 'Season (\\d+)' if crawl_language == 'english' else 'Staffel (\\d+)'

    def parse(self, response):
        link = 'http://serienjunkies.org/serie/{}'
        plex_tv_library_name = self.config['plex']['tv_library_name']

        for series in self.config['series']:
            # build series link from link suffix in config
            series_link = link.format(series['link_suffix'])
            # get existing episodes of series from plex
            existing_episodes = get_existing_episodes(self.plex, plex_tv_library_name, series_name=series['name'])

            # build next request
            request = scrapy.Request(series_link, callback=self.parse_series_landing_page)
            # add series title and existing episodes to request for next callback
            request.meta['series'] = series
            request.meta['existing_episodes'] = existing_episodes
            yield request

    def parse_series_landing_page(self, response):
        # get series title and existing episodes from response
        series = response.meta['series']
        existing_episodes = response.meta['existing_episodes']
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
            request = scrapy.Request(season_link, callback=self.parse_series_season)
            request.meta['series'] = series
            request.meta['season_number'] = season_number
            request.meta['existing_episodes'] = existing_episodes

            # skip seasons that are already present in library if only latest episodes is True
            only_latest_episodes = self.config['general']['only_latest_episodes']
            if only_latest_episodes and season_number < latest_episode['season_number']:
                continue

            yield request

    def parse_series_season(self, response):
        series = response.meta['series']
        existing_episodes = response.meta['existing_episodes']

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
        hoster = self.config['serienjunkies']['hoster']
        crawl_results = [(node.xpath('preceding-sibling::strong[not(text()=\'Download:\')]/text()')
                          .extract()[0],  # release title
                          node.css('::attr(href)').extract()[0])  # download link
                         for node in hd_nodes.xpath('child::a[./following-sibling::text()[1][contains(., \'{0}\')]]'
                                                    .format(hoster))]

        # this is necessary because episodes are sorted by quality in ascending order but we want the best quality at
        # the top of the list
        crawl_results.reverse()

        # map crawl results to SeriesEpisodeItem
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
                downloadable_episode = SeriesEpisodeItem(series_name=series['name'], season_number=season_number,
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
            only_latest_episodes = self.config['general']['only_latest_episodes']
            if only_latest_episodes and downloadable_episode > latest_episode \
                    or not only_latest_episodes and downloadable_episode not in existing_episodes:
                yield downloadable_episode


def get_existing_episodes(plex, tv_library_name: str, series_name: str) -> []:
    """
    Get existing episodes of a tv series from plex server database.
    :param plex: Connection to Plex server.
    :param tv_library_name: Name of the TV series library in Plex.
    :param series_name: Name of the tv series.
    :return: List of existing episodes.
    """
    series_episodes = plex.library.section(tv_library_name).get(series_name).episodes()

    season_episodes = [SeriesEpisodeItem(season_number=int(element.seasonEpisode[1:-3]),
                                         episode_number=int(element.seasonEpisode[4:]),
                                         series_name=element.grandparentTitle,
                                         release_downloadlink_tuples=[])
                       for element in series_episodes]

    return season_episodes
