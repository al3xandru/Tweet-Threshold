import datetime
import logging
import math
import os
import re
import sqlite3
import sys
import urlparse

import jinja2
import requests
import tweepy

from bs4 import BeautifulSoup

logging.basicConfig(filename=os.path.expanduser('~/Library/Logs/com.mypopescu.tweetthreshold.log'),
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)5s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.getLogger('requests').setLevel(logging.WARN)

class Tweets (object):
    def __init__(self, account_data, params):
        auth = tweepy.auth.OAuthHandler(account_data['consumer_key'],
                                        account_data['consumer_secret'])
        auth.set_access_token(account_data['access_token_key'],
                              account_data['access_token_secret'])
        self.api = tweepy.API(auth)
        self.db = params['db']
        self.tweets = []

    def fetch(self):
        _cont = True
        _maxid = None

        while _cont:
            try:
                if _maxid:
                    results = self.api.home_timeline(count=100, include_rts=0, max_id=_maxid)
                else:
                    results = self.api.home_timeline(count=100, include_rts=0)
            except tweepy.TweepError, terr:
                printf('ERROR', "%s", terr)
                break
            _count = 0
            printf('DEBUG', "Getting home_timeline with max_id: %s", _maxid)

            for tweet in results:
                if (not _maxid) or (_maxid and _maxid > tweet.id_str):
                    _maxid = tweet.id_str

                try:
                    url = tweet.entities['urls'][0]['expanded_url']
                except IndexError:
                    url = False
                if url:
                    try:
                        self.tweets.append((
                            tweet.id_str,
                            tweet.user.screen_name,
                            tweet.user.name,
                            tweet.text,
                            url,
                            '',
                            str(tweet.created_at).replace(' ', 'T'),
                            tweet.retweet_count,
                            tweet.favorite_count,
                            tweet.user.followers_count))
                        _count += 1
                    except Exception, ex:
                        printf('WARN', "Tweet https://twitter.com/%s/status/%s skipped because of %s",
                               tweet.user.screen_name, tweet.id_str, ex)

            printf('DEBUG', "Fetched: %s tweets %s containing links. New max_id: %s",
                   len(results), _count, _maxid)
            logging.debug("Fetched: %s tweets %s containing links.", len(results), _count)

            if len(results) < 2:
                _cont = False

    def save(self):
        tdb = TweetDatabase(self.db)
        tdb.save(self.tweets)
        tdb.purge()
        logging.debug("Saved: %s tweets", len(self.tweets))

    def extract_urls(self, text):
        text = re.sub('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|'
                      '[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '',
                      text).strip()
        text = re.sub('\:$', '', text)
        return text


class TweetDatabase (object):
    def __init__(self, db):
        self.conn = sqlite3.connect(db)
        self.conn.row_factory = sqlite3.Row
        self.c = self.conn.cursor()

    def create(self):
        try:
            self.c.execute('CREATE TABLE tweets'
                           '(id int not null unique, '
                           'screen_name text, '
                           'user_name text, '
                           'text text, '
                           'url text, '
                           'title text, '
                           'created_at text, '
                           'retweet_count int, '
                           'fav_count int, '
                           'followers_count int);')
            self.conn.commit()
            return True
        except sqlite3.OperationalError:
            return False

    def load(self):
        self.c.execute('select * from tweets;')
        d = self.c.fetchall()
        tweets = []
        for row in d:
            tweets.append(dict(zip(row.keys(), row)))
        return tweets

    def save(self, data):
        self.create()
        self.c.executemany('INSERT OR REPLACE INTO tweets '
                           'VALUES (?,?,?,?,?,?,?,?,?, ?);', data)
        self.conn.commit()
        return True

    def update(self, data):
        self.c.execute('UPDATE tweets set url=?, title=? where id=?;',
                       data)
        self.conn.commit()
        return True

    def purge(self):
        self.c.execute('''delete from tweets
                          where datetime(created_at) <
                          date('now','-30 day');''')
        self.c.execute('vacuum;')
        self.conn.commit()
        return True


class FilteredTweets (object):
    def __init__(self, params):
        self.filtered_tweets = []
        self.blacklist = params['blacklist']
        self.whitelist = params['whitelist']
        self.db = TweetDatabase(params['db'])
        self.tweets = self.db.load()

        for tweet in self.tweets:
            if self.check_whitelist(tweet['screen_name']):
                score = 1.0
            elif self.check_blacklist(tweet['text']):
                score = self.build_score(tweet['retweet_count'],
                                         tweet['fav_count'],
                                         tweet['followers_count'])
                tweet['score'] = score
                if tweet['score'] > 0:
                    self.filtered_tweets.append(tweet)

        self.filtered_tweets = sorted(self.filtered_tweets,
                                      key=lambda tup: tup['score'],
                                      reverse=True)
        self.resolve_links()

    def resolve_links(self):
        _titles_new = 0
        _titles_existing = 0
        _titles_failed = 0

        for tweet in self.filtered_tweets:
            if not tweet.get('title', None):
                try:
                    response = requests.head(tweet['url'], allow_redirects=True)
                    _ctype = response.headers.get('content-type', '')
                    tweet['url'] = response.url

                    if response.status_code == 200:
                        _titles_new += 1

                        if _ctype.startswith('text'):
                            response = requests.get(tweet['url'], allow_redirects=True)
                            tweet['title'] = self.get_title(response.text, tweet['url'], _ctype)
                        else:
                            tweet['title'] = self.get_title('', tweet['url'], _ctype)

                        self.db.update((tweet['url'], tweet['title'], tweet['id']))
                        printf('DEBUG', "New title: '%s' for '%s'", tweet['title'].encode('utf8'), tweet['url'].encode('utf8'))
                    else:
                        _titles_failed += 1
                        tweet['title'] = self.get_title('', tweet['url'], _ctype)                        
                        printf('INFO', "Non 200 response for '%s': %s", tweet['url'], response.status_code)
                except Exception, exc:
                    _titles_failed += 1
                    tweet['title'] = self.get_title('', tweet['url'], '')
                    printf('WARN', "Error fetching '%s': %s", tweet['url'].encode('utf8'), exc)
            else:
                _titles_existing += 1
                printf('DEBUG', "Existing title '%s' for '%s'", tweet['title'].encode('utf8'), tweet['url'].encode('utf8'))
        logging.debug("Processed %s tweets: %s new titles, %s existing titles, %s failed",
            len(self.filtered_tweets), _titles_new, _titles_existing, _titles_failed)


    def check_blacklist(self, text):
        for phrase in self.blacklist:
            if phrase.strip() in text:
                return False
        return True

    def check_whitelist(self, screen_name):
        for whitelist_name in self.whitelist:
            if screen_name == whitelist_name:
                return True
        return False

    def build_score(self, retweet_count, fav_count, followers_count):
        if retweet_count + fav_count > 2:
            score = ((float(retweet_count) * 10000) + (float(fav_count) * 5000)) / followers_count
            score = round(math.log(score) / 3, 2)
            if score > .99:
                score = .99
        else:
            score = 0
        return score

    def original_build_score(self, retweet_count, followers_count):
        if retweet_count > 2:
            numerator = float(retweet_count)
            denominator = followers_count
            score = (numerator/denominator)*10000
            score = round(math.log(score)/3,2)
            if score > .99:
                score = .99
        else:
            score = 0
        return score

    def load_by_date(self, close, far, params):
        self.date_filtered_tweets = []
        for tweet in self.filtered_tweets:
            tweet['created_at_date'] = datetime.datetime.strptime(tweet['created_at'], '%Y-%m-%dT%H:%M:%S')
            if (build_date(close) > tweet['created_at_date'] > build_date(far)):
                self.date_filtered_tweets.append(tweet)
        return self.date_filtered_tweets

    def get_contenttype(self, ctype):
        if not(ctype):
            return ''
        bits = ctype.split('/')
        if len(bits) == 1:
            return ctype.lower()
        else:
            return bits[1].split(';')[0].lower()


    def get_title(self, body, url, content_type):
        ctype = self.get_contenttype(content_type)

        if body.strip():
            soup = BeautifulSoup(body)
            title = soup.find('title')
            if not title:
                title = soup.find('h1')
            if title:
                return title.get_text().replace('\n', ' ').strip()
            elif ctype:
                return "%s (%s)" % (urlparse.urlsplit(url).netloc, self.get_contenttype(ctype))
            else:
                return urlparse.urlsplit(url).netloc
        elif ctype:
            return "%s (%s)" % (urlparse.urlsplit(url).netloc, self.get_contenttype(ctype))
        else:
            return urlparse.urlsplit(url).netloc

                
class WebPage (object):

    def build(self, yesterdays_items, params):
        with open(params['html_template']) as f:
            template = jinja2.Template(f.read())
        self.html_output = template.render(yesterdays_items=yesterdays_items[:params['threshold']],
                                           count=params['threshold'],
                                           total_count=len(yesterdays_items))
        with open(params['html_output'], 'w') as f:
            f.write(self.html_output.encode('utf-8'))

        logging.info("Output page '%s' written", params['html_output'])

def build_date(day_delta):
    return (datetime.datetime.today() - datetime.timedelta(days=day_delta)).replace(hour=0, minute=0, second=0, microsecond=0)

def printf(level, msg, *args):
    msg = "[%s] %s" % (level, msg)
    if not args:
        print(msg)
    else:
        print(msg % args)

def main(accounts, params, close=0):
    logging.info("Processing %s accounts for %s", len(accounts), 
        build_date(close+1).strftime('%a.%dth, %b.'))

    for account in accounts:
        remote_tweets = Tweets(account, params)
        remote_tweets.fetch()
        remote_tweets.save()

    tweets = FilteredTweets(params)
    wp = WebPage()
    wp.build(tweets.load_by_date(close, 1, params), params)


if __name__ == '__main__':
    from settings import TWITTER_ACCOUNTS, CONFIG

    close = 0
    try:
        close = -1 if 'today' == sys.argv[1] else 0
    except:
        pass

    try:
        main(TWITTER_ACCOUNTS, CONFIG, close)
    except Exception, ex:
        logging.exception('Failed to complete')
