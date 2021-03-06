# -*- coding: utf-8 -*-
import html
import json
import os
import re
from urllib import parse

import scrapy
from scrapy.spiders import CrawlSpider

from collector.items import SingerItem, SongItem


class AdaCrawlSpider(CrawlSpider):

    def __init__(self, singer=None):
        super(AdaCrawlSpider, self).__init__()
        self.__singer = singer

    # https://y.qq.com/portal/search.html#page=1&searchid=1&remoteplace=txt.yqq.top&t=song&w=%E8%AE%B8%E5%B5%A9
    # https://y.qq.com/n/yqq/singer/000CK5xN3yZDJt.html
    # https://y.qq.com/n/yqq/song/004Sktnw0KnoIF.html
    # https://y.qq.com/n/yqq/mv/v/y00119yn6bd.html

    name = 'Ada'
    allowed_domains = ['qq.com']
    start_urls = [
        'https://c.y.qq.com/soso/fcgi-bin/client_search_cp?ct=24&qqmusic_ver=0&new_json=1'
        '&remoteplace=txt.yqq.center&searchid=0&t=0&aggr=1&cr=1&catZhida=1&lossless=0&flag_qc=0'
        '&{p_page_idx}'
        '&{n_page_no}'
        '&{w_singer}'
        '&g_tk=0&jsonpCallback=MusicJsonCallback9260186144153801&loginUin=0&hostUin=0'
        '&format=jsonp&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq&needNewC',
    ]

    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Referer": "https://y.qq.com/portal/search.html"
    }

    singer_url = 'https://y.qq.com/n/yqq/singer/{singer_mid}.html'
    song_url = 'https://y.qq.com/n/yqq/song/{song_mid}.html'
    mv_url = 'https://y.qq.com/n/yqq/mv/v/{song_vid}.html'
    page_url = 'https://c.y.qq.com/v8/fcg-bin/fcg_v8_singer_track_cp.fcg' \
               '?g_tk=5381&loginUin=0&hostUin=0&format=json' \
               '&inCharset=utf8&outCharset=utf-8&notice=0' \
               '&platform=yqq.json&needNewCode=0' \
               '&singermid={singer_mid}' \
               '&order=listen' \
               '&begin={list_start_idx}' \
               '&num={list_no}' \
               '&songstatus=1'
    lyric_url = 'https://c.y.qq.com/lyric/fcgi-bin/fcg_query_lyric_yqq.fcg?nobase64=1' \
                '&musicid={song_id}' \
                '&-=jsonp1&g_tk=5381&loginUin=0&hostUin=0&format=json' \
                '&inCharset=utf8&outCharset=utf-8&notice=0&platform=yqq.json&needNewCode=0'

    page_idx = 1
    page_no = 30

    def start_requests(self):
        yield scrapy.Request(self.start_urls[0].format(
            p_page_idx=parse.urlencode({'p': self.page_idx}),
            n_page_no=parse.urlencode({'n': self.page_no}),
            w_singer=parse.urlencode({'w': self.__singer})
        ), callback=self.parse_singer)

    # rules = (
    #     Rule(LinkExtractor(allow=r'https://y.qq.com/n/yqq/singer/.+'), callback='parse_item', follow=True),
    # )

    def parse_singer(self, response):
        resp = response.body[34: -1]
        result = json.loads(resp)
        singer = SingerItem()

        # get singer's info
        # the difference between dict.get(key) and dict[key]
        singer['singer_id'] = result['data']['zhida']['zhida_singer']['singerID']
        singer['singer_mid'] = result['data']['zhida']['zhida_singer']['singerMID']
        singer['singer_name'] = result['data']['zhida']['zhida_singer']['singerName']
        singer['singer_pic'] = result['data']['zhida']['zhida_singer']['singerPic']
        singer['singer_album_num'] = result['data']['zhida']['zhida_singer']['albumNum']
        singer['singer_mv_num'] = result['data']['zhida']['zhida_singer']['mvNum']
        singer['singer_song_num'] = result['data']['zhida']['zhida_singer']['songNum']

        # store_path = 'resources'
        # if not os.path.exists(store_path):
        #     os.mkdir(store_path)
        # with open('resources/singer.json', 'a+') as f:
        #     # convert singer's attributes to dict, then write to file
        #     f.write(json.dumps(singer.__dict__) + '\n')

        # basing singer's info, to traverse all songs
        for i in range(1, int(singer['singer_song_num']) // self.page_no + 2):
            yield scrapy.Request(self.page_url.format(
                singer_mid=singer['singer_mid'],
                list_start_idx=(i - 1) * self.page_no,
                list_no=self.page_no,
            ), meta={'singer': singer['singer_name'], 'page_idx': i}, callback=self.parse_song_page)

    def parse_song_page(self, response):
        # store_path = 'resources/singer/%s' % response.meta['singer']
        # if not os.path.exists(store_path):
        #     os.mkdir(store_path)
        # with open("%s/%s-page-%s.json"
        #           % (store_path, response.meta['singer'], response.meta['page_idx']), 'wb') as f:
        #     f.write(response.body)
        for i in self.song_generator(response.body):
            yield scrapy.Request(self.lyric_url.format(song_id=i['song_id']),
                                 meta={'song_name': i['song_name'],
                                       'singer': response.meta['singer']
                                       },
                                 callback=self.parse_lyric)

    @staticmethod
    def parse_lyric(response):
        store_path = 'resources/lyric/%s' % response.meta['singer']
        if not os.path.exists(store_path):
            os.mkdir(store_path)
        lyric_json = json.loads(response.body)
        if 'lyric' in dict(lyric_json).keys():
            # html decode
            lyric = html.unescape(lyric_json['lyric'])
            # remove time info , such as [00:03.24]
            lyric = re.sub(r'\[\d{2}:\d{2}.\d{2}\]', '', lyric)
            # replace &apos; with '
            lyric = re.sub(r'&apos;', '\'', lyric)
            # replace &amp; with &
            lyric = re.sub(r'&amp;', '&', lyric)
            # remove some sign
            lyric = re.sub(r'(\[ti:)|(\[ar:)|(\[al:)|(\[by:)|(\[offset:\d*\])|(\[)|(\])', '', lyric)
            # remove not lyric
            lyric = re.sub(u'此歌曲为没有填词的纯音乐，请您欣赏', '', lyric)
            # remove redundant empty line
            lyric = re.sub(r'([\r\n]{2,})|((\r\n){2,})', '\n', lyric)
            with open('%s/%s.txt' % (store_path, response.meta['singer']), 'a+', encoding='utf-8') as f:
                f.write(lyric + '\n\n\n\n')

    @staticmethod
    def song_generator(resp):
        song = SongItem()
        resp = json.loads(resp)
        for i in resp['data']['list']:
            song['song_id'] = i['musicData']['songid']
            song['song_mid'] = i['musicData']['songmid']
            song['song_name'] = i['musicData']['songname']
            song['song_vid'] = i['musicData']['vid']
            yield song
