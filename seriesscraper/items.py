# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class SeriesscraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class SeriesEpisodeDownloadItem(scrapy.Item):
    series_name = scrapy.Field()
    season_number = scrapy.Field()
    episode_number = scrapy.Field()
    download_link = scrapy.Field()
