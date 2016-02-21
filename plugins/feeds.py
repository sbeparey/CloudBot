import asyncio
import feedparser
import functools
import re
import time

from datetime import datetime

from collections import defaultdict

from cloudbot import hook
from cloudbot.event import EventType
from cloudbot.util import database, web, formatting


from sqlalchemy import Table, Column, String, Integer, PrimaryKeyConstraint, desc
from sqlalchemy.sql import select, insert, delete

from sqlalchemy.exc import IntegrityError

from bs4 import BeautifulSoup

t = 'https://www.reddit.com/r/'
subs = defaultdict(list)
cache = defaultdict(list)
feed = defaultdict(list)
status = defaultdict(int)

feed_subs = Table(
    'feed_subs',
    database.metadata,
    Column('channel', String(25)),
    Column('subs', String(255)),
    PrimaryKeyConstraint('channel', 'subs')
)

@asyncio.coroutine
@hook.on_start()
def initial_load(db, message):
    """ When the script starts, build the url and cache the initial feed """
    global subs, status
    all_subs = get_all_subs(db)
    if not all_subs:
        return
    for row in all_subs:
        chan = row['channel']
        dbsubs = row['subs'] 
        status[chan] = 1
        subs[chan] = dbsubs.split('+')
        url = '{}{}/new/.rss?sort=new'.format(t, dbsubs)
        get_feed(url, chan)

@hook.periodic(600, initial_interval=600)
def refresh_feed(db):
    for chan in subs:
        url = '{}{}/new/.rss?sort=new'.format(t, '+'.join(subs[chan]))
        update_feed(url, chan)

def get_feed(url, chan):
    """ Grab the entries from the feed and cache them """
    global cache
    f = feedparser.parse(url)
    if f:
        cache[chan] = f.entries
        feed[chan] = f.entries[:3]

def update_feed(url, chan):
    """ Update the existing feed cache with latest entries """
    global cache, feed
    new_feed = feedparser.parse(url)
    if new_feed:
        for new_item in new_feed.entries:
            for old_item in cache[chan]:
                if get_url_id(new_item.link) != get_url_id(old_item.link):
                    cache[chan].append(new_item)
                    feed[chan].append(new_item)

@hook.periodic(60, initial_interval=60)
def display_feed_item(bot):
    global feed
    conn = bot.connections['snoonet']
    if conn.ready:
        for chan in subs:
            if feed.get(chan) and status[chan] == 1:
                item = feed[chan].pop()
                display_text = format_feed(item)
                conn.message(chan, display_text)

def get_url_id(link):
    return link.split('comments/')[1].split('/')[0]

def format_feed(item):
    url_id = get_url_id(item.link)
    url = "https://redd.it/{}".format(url_id)
    title = formatting.strip_html(item.title)
    author = item.author_detail.name
    sub = item.tags[0].label
    soup = BeautifulSoup(item.content[0].value)
    link = soup.find('a', text='[link]')['href']
    if link == item.link:
        return "\x0312{}\x03: \x0311,01{}\x03 in {} by \x02{}\x02 [ {} ]".format('Self post', title, sub, author, url)
    else:
        return "\x0313{}\x03: \x0311,01{}\x03 in {} by \x02{}\x02 [ {} ] {}".format('Link post', title, sub, author, url, link)

def format_item(item):
    url = web.try_shorten(item.link)
    title = formatting.strip_html(item.title)
    return "{} ({})".format(title, url)

def list_to_url(chan):
    if not subs.get(chan):
        return "I got nothing!"
    return "{}{}/new".format(t, '+'.join(subs[chan]))

def get_all_subs(db):
    query = select([feed_subs])
    return db.execute(query)

def get_subs(db, chan):
    query = select([feed_subs.c.subs]) \
        .where(feed_subs.c.channel == chan) 
    return db.execute(query).fetchone()

def update_subs(db, chan, subs):
    if get_subs(db, chan):
        query = feed_subs.update() \
            .where(feed_subs.c.channel == chan) \
            .values(subs = subs)
    else:
        query = feed_subs.insert().values( \
            channel = chan, \
            subs = subs)
    db.execute(query)
    db.commit()

def list(db, chan):
    global subs
    if chan not in subs:
        chan_subs = get_subs(db, chan)
        if chan_subs:
            for sub in chan_subs[0].split('+'):
                subs[chan].append(sub)

def add(text, db, chan):
    text = text.split('add ').pop()
    if not text.startswith(('r/', '/r/')):
        return "\x02{}\x02 is not a valid subreddit".format(text)

    sub = text.split('r/').pop()
    list(db, chan)
    if sub in subs[chan]:
        return "\x02{}\x02 already exists.".format(text)

    subs[chan].append(sub)
    s = '+'.join(subs[chan])

    update_subs(db, chan, s)
    return "\x02{}\x02 was added.".format(text)

def remove(text, db, chan):
    text = text.split('remove ').pop()
    if not text.startswith(('r/', '/r/')):
        return "\x02{}\x02 is not a valid subreddit".format(text)

    sub = text.split('r/').pop()
    list(db, chan)
    
    try:
        subs[chan].remove(sub)
        s = '+'.join(subs[chan])
        update_subs(db, chan, s)
        return "\x02{}\x02 was removed.".format(text)
    except ValueError:
        return "\x02{}\x02 does not exist!".format(text)

def start(chan):
    global status
    status[chan] = 1
    return "Feed started."

def stop(chan):
    global status
    status[chan] = 0
    return "Feed stopped!"

@hook.command("feed", "rss", "news")
def rss(text, db, chan):
    """<feed> -- Gets the first three items from the RSS/ATOM feed <feed>."""
    limit = 3

    t = text.lower().strip()
    if t == "xkcd":
        addr = "http://xkcd.com/rss.xml"
    elif t == "ars":
        addr = "http://feeds.arstechnica.com/arstechnica/index"
    elif t in ("pypi", "pip", "py"):
        addr = "https://pypi.python.org/pypi?%3Aaction=rss"
        limit = 6
    elif t in ("pypinew", "pipnew", "pynew"):
        addr = "https://pypi.python.org/pypi?%3Aaction=packages_rss"
        limit = 5
    elif t == "world":
        addr = "https://news.google.com/news?cf=all&ned=us&hl=en&topic=w&output=rss"
    elif t in ("us", "usa"):
        addr = "https://news.google.com/news?cf=all&ned=us&hl=en&topic=n&output=rss"
    elif t == "nz":
        addr = "https://news.google.com/news?pz=1&cf=all&ned=nz&hl=en&topic=n&output=rss"
    elif t in ("anand", "anandtech"):
        addr = "http://www.anandtech.com/rss/"
    elif t.startswith(("r/", "/r/")):
        sub = t.split("r/")[1]
        addr = "https://www.reddit.com/r/{}/new/.rss".format(sub)
    elif t.startswith('list'):
        list(db, chan)
        return list_to_url(chan)
    elif t.startswith('add '):
        return add(t, db, chan)
    elif t.startswith('remove '):
        return remove(t, db, chan)
    elif t == 'start':
        return start(chan)
    elif t == 'stop':
        return stop(chan)
    else:
        addr = text

    feed = feedparser.parse(addr)
    if not feed.entries:
        return "Feed not found."

    out = []
    for item in feed.entries[:limit]:
        out.append(format_item(item))

    start = "\x02{}\x02: ".format(feed.feed.title) if 'title' in feed.feed else ""
    return start + ", ".join(out)