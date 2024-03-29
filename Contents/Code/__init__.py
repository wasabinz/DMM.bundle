# -*- coding: utf-8 -*-
import re
import requests

# URLS
DMM_BASE_URL = 'https://www.dmm.co.jp/'
DMM_ITEM_INFO = DMM_BASE_URL + 'digital/videoa/-/detail/=/cid={}/'
DMM_SEARCH_URL = DMM_BASE_URL + 'digital/videoa/-/list/search/=/view=text/?searchstr={}'
DMM_THUMB_URL = 'http://pics.dmm.co.jp/digital/video/{0}/{0}pt.jpg'
DMM_POSTER_URL = 'http://pics.dmm.co.jp/digital/video/{0}/{0}ps.jpg'
DMM_COVER_URL = 'http://pics.dmm.co.jp/digital/video/{0}/{0}pl.jpg'
DMM_ACTOR_URL = 'http://actress.dmm.co.jp/-/detail/=/actress_id={}/'
DMM_SAMPLE_URL = 'http://pics.dmm.co.jp/digital/video/{0}/{0}jp-{1}.jpg'


def Start():
    pass


def log(message, *args, **kwargs):
    """ Writes message to the log file depending on the preferences. """

    if Prefs['debug']:
        Log.Debug(message, *args, **kwargs)


class DMMAgent(Agent.Movies):
    name = 'DMM'
    languages = [Locale.Language.English, Locale.Language.Japanese]
    accepts_from = ['com.plexapp.agents.localmedia']
    primary_provider = True
    cookies = {'age_check_done':'1', 'cklg':'ja'}

    def get_proxies(self):
        """ pull proxy settings from preference. """

        proxies = {}
        if Prefs['httpproxy']:
            proxies['http'] = Prefs["httpproxy"]
        if Prefs['httpsproxy']:
            proxies['https'] = Prefs["httpsproxy"]
        return proxies

    def get_item_from_link(self, item, link):

        item_id = ''
        # extract ID from link
        id_match = re.search('{}=([^/]+)/'.format(item), link)
        if id_match:
            item_id = id_match.group(1)
        return item_id

    def get_actor_photo(self, id):
        url = DMM_ACTOR_URL.format(id)
        log('Aquiring actor url: {}'.format(url))
        proxies = self.get_proxies()
        page = requests.get(url, cookies=self.cookies, proxies=proxies)
        root = HTML.ElementFromString(page.text)

        imgElmt = root.xpath(u'//meta[@property="og:image"]')
        if imgElmt:
            return imgElmt[0].get('content')

    def do_search(self, query):
        """ This function takes the jav id string found in the filename
        as query and searches it in the DMM database. The result is a
        list of dictionary containing item id, url, title and the
        thumbnail url.
        The jav id string should be in the format that is
        searchable by the DMM database. E.g. STAR00611, HODV021050
        """

        proxies = self.get_proxies()
        search_url = DMM_SEARCH_URL.format(query)
        page = requests.get(search_url, proxies=proxies, cookies=self.cookies)
        root = HTML.ElementFromString(page.text)

        found = []
        for r in root.xpath('//p[@class="ttl"]/a'):
            # find link and title to the DMM item
            title = r.text
            murl = r.get('href')
            # pull item id from URL
            item_id = self.get_item_from_link('cid', murl)
            if item_id:
                # generate thumbnail url
                thumb = DMM_THUMB_URL.format(item_id)

                found.append({'item_id': item_id, 'url': murl,
                              'title': title, 'thumb': thumb})

        return found

    def extract_jav_id(self, name):
        """ This function extracts JAV ID in from the name argument and
        returns them as a tuple.
        """

        id_match = re.search(
            r'(?P<code>([a-zA-Z]{2,5})|(T28))[-]?(?P<num>\d{3,6})', name)
        if id_match:

            # jav id is broken up into ID code (the first few letters)
            # and the ID number (the remaining numbers)
            id_code = id_match.group('code').lower()
            id_num = id_match.group('num').lstrip('0')

            return id_code, id_num

    def jav_id_to_str(self, id_code, id_num):
        """ convert JAV ID into normalized form. The code numbers are
        right justified by '0' characters. The amount of justification
        depends on the JAV code.
        """

        rjust_c = 5
        if id_code == 'hodv':
            rjust_c = 6

        return id_code + id_num.rjust(rjust_c, '0')

    def search(self, results, media, lang):

        # Extract id from media filename
        jav_id = self.extract_jav_id(String.Unquote(media.filename))

        if jav_id:

            # Turn id into format that is recognizable by DMM search engine
            id_str = self.jav_id_to_str(*jav_id)

            log('*** SEARCHING "%s" - DMM Plex Agent ***', id_str)
            found = self.do_search(id_str)

            # Write search result status to log
            if found:
                log('Found %s result(s) for query "%s"', len(found), id_str)

                for i, f in enumerate(found, 1):
                    log('\t%s. %s [%s] {%s}', i, f['title'], f['url'], f['thumb'])
            else:
                log('No results found for query "%s"', id_str)
                return

            log('-' * 60)

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

        log('*** UPDATING "%s" - DMM Plex Agent ***', metadata.id)
        try:
            # Make url
            url = DMM_ITEM_INFO.format(metadata.id)
            # fetch HTML
            proxies = self.get_proxies()
            page = requests.get(url, proxies=proxies, cookies=self.cookies)
            root = HTML.ElementFromString(page.text)

            # content rating
            metadata.content_rating = 'R18+'
            # set tagline to URL
            metadata.tagline = url
            # title
            title_elmt = root.xpath('//h1[@id="title"]')
            if title_elmt:
                # metadata.title = title_elmt[0].text
                title_text = title_elmt[0].text
                # unmodified original title
                metadata.original_title = title_text
                # append id to the title if needed
                if Prefs['appendid']:
                    id_code, id_num = self.extract_jav_id(metadata.id)
                    title_text += " ({}{:>03})".format(id_code.upper(), id_num)
                metadata.title = title_text
                log('Title: ' + title_text)

            # release date & year
            date_elmt = root.xpath(
                u'//td[contains(text(),"商品発売日")]/following-sibling::td[1]')
            if date_elmt:
                release_date = Datetime.ParseDate(date_elmt[0].text.strip())
                log('Release date: ' + str(release_date))
                if release_date:
                    metadata.originally_available_at = release_date
                    metadata.year = release_date.year

            # summary
            summary_elmt = root.xpath(u'//div[@class="mg-b20 lh4"]')
            if summary_elmt:
                summary_text = summary_elmt[0].text.strip()
                log('Summary: ' + summary_text)
                metadata.summary = summary_text

            # genre
            metadata.genres.clear()
            genre_elmts = root.xpath(
                u'//td[contains(text(),"ジャンル")]/following-sibling::td[1]/a')
            for g in genre_elmts:
                metadata.genres.add(g.text)

            # actors
            metadata.roles.clear()
            actor_elmts = root.xpath('//span[@id="performer"]/a[@href!="#"]')
            if actor_elmts:
                log('Actor(s): ' + ' '.join(a.text for a in actor_elmts))
                for a in actor_elmts:
                    role = metadata.roles.new()
                    # Add to actor
                    role.name = a.text
                    # Add actor photo
                    actor_id = self.get_item_from_link('id', a.get('href'))
                    role.photo = self.get_actor_photo(actor_id)

            # director
            metadata.directors.clear()
            director_elmts = root.xpath(
                u'//td[contains(text(), "監督")]/following-sibling::td[1]/a')
            if director_elmts:
                log("Director(s): " + ' '.join(d.text for d in director_elmts))
                for d in director_elmts:
                    director = metadata.directors.new()
                    director.name = d.text

            # studio
            studio_elmt = root.xpath(
                u'//td[contains(text(),"メーカー")]/following-sibling::td[1]/a')
            if studio_elmt:
                log('Studio: ' + studio_elmt[0].text)
                metadata.studio = studio_elmt[0].text

            # add series to collection
            if Prefs['addcollection']:
                metadata.collections.clear()
                series_elmts = root.xpath(
                    u'//td[contains(text(),"シリーズ")]/following-sibling::td[1]/a')
                if series_elmts:
                    log("Series: " + ' '.join(s.text for s in series_elmts))
                    for s in series_elmts:
                        metadata.collections.add(s.text)

            # rating (Plex rating is out of 10 while DMM rating is out of 5)
            rating = self.get_rating(root) * 2
            if rating:
                log('Rating: %.1f', rating)
                metadata.rating = rating

            # Posters and cover
            thumb_url = DMM_THUMB_URL.format(metadata.id)
            poster_url = DMM_POSTER_URL.format(metadata.id)
            metadata.posters[poster_url] = Proxy.Preview(
                HTTP.Request(thumb_url), 1)
            cover_url = DMM_COVER_URL.format(metadata.id)
            metadata.posters[cover_url] = Proxy.Media(
                HTTP.Request(cover_url), 2)

            # arts
            smple_c = len(root.xpath(u'//a[@name="sample-image"]'))
            for i in range(1, smple_c + 1):
                smple_url = DMM_SAMPLE_URL.format(metadata.id, i)
                metadata.art[smple_url] = Proxy.Media(
                    HTTP.Request(smple_url, sleep = 0.5))

        except Exception as e:
            Log.Error(
                'Error obtaining data for item with id %s (%s) [%s]', metadata.id, url, e.message)
