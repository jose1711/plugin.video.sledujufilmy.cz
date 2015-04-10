# -*- coding: UTF-8 -*-
# /*
# *      Copyright (C) 2012 Lubomir Kucera
# *
# *
# *  This Program is free software; you can redistribute it and/or modify
# *  it under the terms of the GNU General Public License as published by
# *  the Free Software Foundation; either version 2, or (at your option)
# *  any later version.
# *
# *  This Program is distributed in the hope that it will be useful,
# *  but WITHOUT ANY WARRANTY; without even the implied warranty of
# *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# *  GNU General Public License for more details.
# *
# *  You should have received a copy of the GNU General Public License
# *  along with this program; see the file COPYING.  If not, write to
# *  the Free Software Foundation, 675 Mass Ave, Cambridge, MA 02139, USA.
# *  http://www.gnu.org/copyleft/gpl.html
# *
# */
import urllib
import util
from provider import ContentProvider
from bs4 import BeautifulSoup


class SledujuFilmyContentProvider(ContentProvider):
    urls = {'Filmy': 'http://sledujufilmy.cz', 'Seriály': 'http://serialy.sledujufilmy.cz'}

    def __init__(self, username=None, password=None, filter=None):
        ContentProvider.__init__(self, 'sledujufilmy.cz', self.urls['Filmy'], username, password, filter)
        # Work around April Fools' Day page
        util.init_urllib(self.cache)
        cookies = self.cache.get('cookies')
        if not cookies or len(cookies) == 0:
            util.request(self.base_url)

    def __del__(self):
        util.cache_cookies(self.cache)

    def capabilities(self):
        return ['resolve', 'categories', 'search']

    def categories(self):
        result = []
        for name, url in self.urls.items():
            item = self.dir_item()
            item['title'] = name
            item['url'] = url
            result.append(item)
        return result

    def search(self, keyword):
        return self.list_movies(self.movie_url('/vyhledavani/?search=' + urllib.quote_plus(keyword)))

    def list(self, url):
        if 'serialy.' in url:
            if url.count('#') > 0:
                return self.list_episodes(url)
            elif url.count('/') > 2:
                return self.list_seasons(url)
            return self.list_series(url)
        else:
            if url.count('/') > 2:
                return self.list_movies(url)
            return self.list_genres(url)

    def parse(self, url):
        return BeautifulSoup(util.request(url))

    def movie_url(self, url):
        return self.urls['Filmy'] + url

    def series_url(self, url):
        return self.urls['Seriály'] + url

    def list_genres(self, url):
        result = []
        item = self.dir_item()
        item['title'] = 'Všetky'
        item['url'] = url + '/seznam-filmu/'
        result.append(item)
        for genre in self.parse(url).select('#content .genres .buts a'):
            item = self.dir_item()
            item['title'] = genre.text
            item['url'] = url + genre.get('href')
            result.append(item)
        return result

    def list_movies(self, url):
        result = []
        tree = self.parse(url)
        for movie in tree.select('#content .mlist--list .item'):
            if not movie.find('span', 'top'):
                item = self.video_item()
                item['title'] = movie.select('.info h3')[0].text
                item['url'] = self.movie_url(movie.select('.info .ex a')[0].get('href'))
                item['img'] = self.movie_url(movie.select('.img--container img')[0].get('src'))
                result.append(item)
        active_page = tree.select('#content .pagination .active')
        if len(active_page) > 0:
            next_page = active_page[0].find_next_sibling('a')
            if next_page:
                item = self.dir_item()
                item['type'] = 'next'
                item['url'] = self.movie_url(next_page.get('href'))
                result.append(item)
        return result

    def list_series(self, url):
        result = []
        url += '/abecedni-seznam/'
        while len(url) > 0:
            tree = self.parse(url)
            for series in tree.select('#content .movies_list a.item'):
                item = self.dir_item()
                item['title'] = series.h3.text
                item['url'] = self.series_url(series.get('href'))
                item['img'] = self.series_url(series.img.get('src'))
                result.append(item)
            active_page = tree.select('#content .pagination .active')
            if len(active_page) > 0:
                next_page = active_page[0].find_next_sibling('a')
                if next_page:
                    url = self.series_url(next_page.get('href'))
                    continue
            url = ''
        return result

    def list_seasons(self, url):
        result = []
        for season in self.parse(url).select('#episodes--list a.accordionTitle'):
            item = self.dir_item()
            item['title'] = season.text.split(' - ', 1)[1]
            item['url'] = url + '#' + item['title'].split('. ', 1)[0]
            result.append(item)
        return result

    def list_episodes(self, url):
        result = []
        url, season = url.split('#', 1)
        for episode in self.parse(url).select('#episodes--list dd:nth-of-type(' + season +
                                              ') ul.episodes li'):
            link = episode.find('a', 'view')
            link.extract()
            item = self.video_item()
            item['title'] = episode.text.strip()
            item['url'] = self.series_url(link.get('href'))
            item['number'] = int(item['title'].split('.', 1)[0])
            result.append(item)
        return sorted(result, key=lambda k: k['number'])

    def resolve(self, item, captcha_cb=None, select_cb=None):
        streams = []
        link = self.parse(item['url']).find('a', {'class': ['play-movie', 'play-epizode']})
        if link and link.get('data-loc'):
            url = 'http://stream-a-ams1xx2sfcdnvideo5269.cz/'
            if 'serialy.' in item['url']:
                url += 'prehravac.php?play=serail&id='
            else:
                url += 'okno.php?new_way=yes&film='
            url += link.get('data-loc')
            for container in self.parse(url).select('.container .free--box'):
                for stream in container.find_all(['embed', 'object', 'iframe', 'script']):
                    for attribute in ['src', 'data']:
                        value = stream.get(attribute)
                        if value:
                            streams.append(value)
            result = self.findstreams(streams)
            if len(result) == 1:
                return result[0]
            elif len(result) > 1 and select_cb:
                return select_cb(result)
        return None
