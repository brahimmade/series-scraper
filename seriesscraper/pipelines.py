# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html
from myjdapi import myjdapi

from seriesscraper.config import load_config
from seriesscraper.items import SeriesEpisodeDownloadItem


class JDownloaderPipeline(object):
    def __init__(self):
        self.config = load_config()

        myjd_email = self.config['item_pipelines']['myjdownloader']['email']
        myjd_password = self.config['item_pipelines']['myjdownloader']['password']
        myjd_device = self.config['item_pipelines']['myjdownloader']['device_name']

        self.jd = myjdapi.Myjdapi()
        self.jd.connect(myjd_email, myjd_password)
        self.jd_device = self.jd.get_device(myjd_device)

    def process_item(self, item, spider):
        assert isinstance(item, SeriesEpisodeDownloadItem)

        series_name = item['series_name']
        season_number = '{num:02d}'.format(num=item['season_number'])
        episode_number = '{num:02d}'.format(num=item['episode_number'])
        download_link = item['download_link']

        link_params = []
        link_params.append({
            'autostart': self.config['item_pipelines']['myjdownloader']['autostart_downloads'],
            'links': download_link,
            'packageName': '{} S{}E{}'.format(series_name, season_number, episode_number),
            'extractPassword': 'serienjunkies.org',
            'priority': 'DEFAULT',
            'downloadPassword': None,
            'destinationFolder': '{}/{}'.format(self.config['item_pipelines']['myjdownloader']['tvseries_dir'], series_name),
            'overwritePackagizerRules': True
        })

        self.jd_device.linkgrabber.add_links(link_params)
