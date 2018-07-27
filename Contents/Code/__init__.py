# -*- coding: utf-8 -*-
import re
import requests
import types
from datetime import datetime

ART = 'dmm-content-icon.png'
ICON = 'icon-default.png'

# URLS
VERSION_NO = '0.2015.8.17.0'
DMM_BASE_URL = 'http://www.dmm.co.jp/'
DMM_ITEM_INFO = DMM_BASE_URL + 'digital/videoa/-/detail/=/cid={}/'
DMM_SEARCH_URL = DMM_BASE_URL + \
    'search/?category=digital_videoa&searchstr=%s&analyze=V1EBDFYOUAU_&redirect=1&sort=date&limit=30&view=text&enc=UTF-8&commit=%%E6%%A4%%9C%%E7%%B4%%A2'
DMM_THUMB_URL = 'http://pics.dmm.co.jp/digital/video/{0:s}/{0:s}pt.jpg'
DMM_POSTER_URL = 'http://pics.dmm.co.jp/digital/video/{0:s}/{0:s}ps.jpg'
DMM_COVER_URL = 'http://pics.dmm.co.jp/digital/video/{0:s}/{0:s}pl.jpg'
DMM_ACTOR_URL = 'http://actress.dmm.co.jp/-/detail/=/actress_id={}/'


def Start():
    pass


class DMMAgent(Agent.Movies):
    name = 'DMM'
    languages = [Locale.Language.NoLanguage]
    accepts_from = ['com.plexapp.agents.localmedia']
    primary_provider = True

    def log(self, message, *args, **kwargs):
        """ Writes message to the log file. """

        if Prefs['debug']:
            Log.Debug(message, *args, **kwargs)

    def get_proxies(self):
        """ pull proxy settings from preference. """

        proxies = {}
        if Prefs['httpproxy'] is not None:
            proxies['http'] = Prefs["httpproxy"]
        if Prefs['httpsproxy'] is not None:
            proxies['https'] = Prefs["httpsproxy"]
        return proxies

    def get_item_from_link(self, item, link):

        item_id = ''
        # extract ID from link
        id_match = re.search('{}=([^/]+)/'.format(item), link)
        if id_match:
            item_id = id_match.group(1)
        return item_id

    def get_actor_photo(self, id, name):
        url = DMM_ACTOR_URL.format(id)
        proxies = self.get_proxies()
        page = requests.get(url, proxies=proxies)
        root = HTML.ElementFromString(page.text)

        imgElmt = root.xpath('//img[@alt="%s"]' % name)
        if imgElmt:
            return imgElmt[0].get('src')

    def do_search(self, query):
        """ This function takes the jav id string found in the filename 
        as query and searches it in the DMM database. The result is a 
        list of dictionary containing item id, url, title and the 
        thumbnail url. 
        The jav id string should be in the format that is
        searchable by the DMM database. E.g. STAR00611, HODV021050
        """

        proxies = self.get_proxies()
        search_url = DMM_SEARCH_URL % query
        page = requests.get(search_url, proxies=proxies)
        root = HTML.ElementFromString(page.text)

        found = []
        for r in root.xpath('//p[@class="ttl"]/a'):
            # find link and title to the DMM item
            title = r.text
            murl = r.get('href')
            # pull item id from URL
            item_id = self.get_item_from_link('cid', murl)
            if not item_id:
                continue
            # generate thumbnail url
            thumb = DMM_THUMB_URL.format(item_id, item_id)

            found.append({'item_id': item_id, 'url': murl,
                          'title': title, 'thumb': thumb})

        return found

    def extract_jav_id(self, name):
        """ This function extracts JAV ID in from the name argument.
        The output will be a normalized form of the JAV ID found in the
        argument.
        """

        jav_id = ''
        id_match = re.search(r'(([a-zA-Z]{2,5})|(T28))[-]?(\d{3,6})', name)
        if id_match:

            # jav id is broken up into ID code (the first few letters)
            # and the ID number (the remaining numbers)
            id_code = id_match.group(1).lower()
            id_num = id_match.group(4)

            # convert JAV ID into normalized form. The code numbers are
            # right justified by '0' characters. The amount of justific-
            # ation is dependent on the JAV code.
            rjust_c = 5
            if id_code == 'hodv':
                rjust_c = 6

            jav_id = id_code + id_num.rjust(rjust_c, '0')

        return jav_id

    def search(self, results, media, lang):

        # Extract id from media filename
        jav_id = self.extract_jav_id(String.Unquote(media.filename))

        if jav_id:
            self.log('***** SEARCHING FOR "%s" - DMMAgent v.%s *****',
                     jav_id, VERSION_NO)
            found = self.do_search(jav_id)

            # Write search result status to log
            if found:
                self.log('Found %s result(s) for query "%s',
                         len(found), jav_id)

                for i, f in enumerate(found, 1):
                    self.log('    %s. %s [%s] {%s}', i,
                             f['title'], f['url'], f['thumb'])
            else:
                self.log('No results found for query "%s"', jav_id)
                return

            self.log('-' * 60)

            # walk the found items and gather extended information
            score = 100
            for f in found:
                # evaluate the score by using rudementary first come first
                # serve method.
                results.Append(MetadataSearchResult(
                    id=f['item_id'], name=f['title'], score=score, thumb=f['thumb'], lang=lang))
                if score >= 5:
                    score = score - 5

    def get_rating(self, root):
        """ Searches for the rating element from the root element tree
        of a DMM item info page. 
        """

        rating = 0.0
        rating_elmt = root.xpath('//p[@class="d-review__average"]/strong')
        if rating_elmt:
            # The rating will be a floating point number in string
            rating_match = re.search(r'\d([.]\d+)?', rating_elmt[0].text)
            if rating_match:
                rating = float(rating_match.group())

        return rating

    def update(self, metadata, media, lang):

        self.log('***** UPDATING "%s" ID: %s - DMMAgent v.%s *****',
                 media.title, metadata.id, VERSION_NO)
        try:
            # Make url
            url = DMM_ITEM_INFO.format(metadata.id)
            # fetch HTML
            proxies = self.get_proxies()
            page = requests.get(url, proxies=proxies)
            root = HTML.ElementFromString(page.text)

            # content rating
            metadata.content_rating = 'X'
            # set tagline to URL
            metadata.tagline = url
            # title
            title_elmt = root.xpath('//h1[@id="title"]')
            if title_elmt:
                self.log('Title: ' + title_elmt[0].text)
                metadata.title = title_elmt[0].text

            # release date & year
            date_elmt = root.xpath(
                u'//td[contains(text(),"商品発売日")]/following-sibling::td[1]')
            if date_elmt:
                date_str = date_elmt[0].text.strip()
                if '----' in date_str:
                    # if the first date is not available, choose another date field
                    date_elmt = root.xpath(
                        u'//td[contains(text(),"配信開始日")]/following-sibling::td[1]')
                    if len(date_elmt):
                        date_str = date_elmt[0].text.strip()

                self.log('Release date: ' + date_str)
                # parse date string into date object
                release_date = Datetime.ParseDate(date_str)
                if release_date:
                    metadata.originally_available_at = release_date
                    metadata.year = release_date.year

            # summary (the xpath might need to be updated when website
            # changes its layout)
            summary_elmt = root.xpath(u'//div[@class="mg-b20 lh4"]')
            if summary_elmt:
                summary_text = summary_elmt[0].text.strip()
                self.log('Summary: ' + summary_text)
                metadata.summary = summary_text

            # genre
            genre_filter = list()
            if Prefs["excludegenre"]:
                genre_filter = String.Unquote(Prefs["excludegenre"]).split(';')
            metadata.genres.clear()
            genre_elmts = root.xpath(
                u'//td[contains(text(),"ジャンル")]/following-sibling::td[1]/a')
            for g in genre_elmts:
                if g.text not in genre_filter:
                    metadata.genres.add(g.text)

            # actors
            metadata.roles.clear()
            actor_elmts = root.xpath('//span[@id="performer"]/a[@href!="#"]')
            if actor_elmts:
                self.log('Actor(s): ' +
                         ' '.join([a.text for a in actor_elmts]))
                for a in actor_elmts:
                    role = metadata.roles.new()
                    # Add to actor
                    role.name = a.text
                    # Add actor photo
                    actor_id = self.get_item_from_link('id', a.get('href'))
                    role.photo = self.get_actor_photo(actor_id, a.text)

            # director
            metadata.directors.clear()
            director_elmts = root.xpath(
                u'//td[contains(text(), "監督")]/following-sibling::td[1]/a')
            if director_elmts:
                self.log("Director(s): " +
                         ' '.join([d.text for d in director_elmts]))
                for d in director_elmts:
                    metadata.directors.add(d.text)

            # studio
            studio_elmt = root.xpath(
                u'//td[contains(text(),"メーカー")]/following-sibling::td[1]/a')
            if studio_elmt:
                self.log('Studio: ' + studio_elmt[0].text)
                metadata.studio = studio_elmt[0].text

            # add series to collection
            metadata.collections.clear()
            series_elmts = root.xpath(
                u'//td[contains(text(),"シリーズ")]/following-sibling::td[1]/a')
            if series_elmts:
                self.log("Series(s): " +
                         ' '.join([s.text for s in series_elmts]))
                for s in series_elmts:
                    metadata.collections.add(s.text)

            # rating (Plex rating is out of 10 while DMM rating is out
            # of 5)
            rating = metadata.rating = self.get_rating(root) * 2
            if rating:
                self.log('Rating: {:.1f}'.format(rating))
                metadata.rating = rating

            # Posters
            thumb_url = DMM_THUMB_URL.format(metadata.id)
            poster_url = DMM_POSTER_URL.format(metadata.id)
            metadata.posters[poster_url] = Proxy.Preview(
                HTTP.Request(thumb_url))

        except Exception as e:
            Log.Error(
                'Error obtaining data for item with id %s (%s) [%s] ', metadata.id, url, e.message)
