# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html
from typing import Any

import scrapy


class SeriesscraperItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass


class EpisodeItem(scrapy.Item):
    tv_show_name = scrapy.Field()
    season_number = scrapy.Field()
    episode_number = scrapy.Field()
    release_downloadlink_tuples = scrapy.Field()

    def __new__(cls, season_number: int, episode_number: int, *args, **kwargs) -> Any:
        # For some reason, __hash__ is called before __init__ of the super class 'DictItem'. Because of this,
        # the attribute _value of DictItem is not instantiated when __hash__ is called. However, __hash__ relies on
        # a properly initiated _value attribute, because __hash__ uses the __getitem__ method of DictItem which in turn
        # uses _value['field'] to retrieve the value.
        # To fix this, I included this hack that prematurely instantiates the _values attribute and populates it with
        # the needed values for __hash__.
        cls._values = {'season_number': season_number, 'episode_number': episode_number}
        return super().__new__(cls)

    def __hash__(self) -> int:
        return hash((self.get('season_number'), self.get('episode_number')))

    def __eq__(self, other):
        return (self.get('season_number'), self.get('episode_number')) == \
               (other.get('season_number'), other.get('episode_number'))

    def __ne__(self, other):
        return (self.get('season_number'), self.get('episode_number')) != \
               (other.get('season_number'), other.get('episode_number'))

    def __lt__(self, other):
        return (self.get('season_number'), self.get('episode_number')) < \
               (other.get('season_number'), other.get('episode_number'))

    def __le__(self, other):
        return (self.get('season_number'), self.get('episode_number')) <= \
               (other.get('season_number'), other.get('episode_number'))

    def __gt__(self, other):
        return (self.get('season_number'), self.get('episode_number')) > \
               (other.get('season_number'), other.get('episode_number'))

    def __ge__(self, other):
        return (self.get('season_number'), self.get('episode_number')) >= \
               (other.get('season_number'), other.get('episode_number'))
