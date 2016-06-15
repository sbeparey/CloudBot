import asyncio
import functools
import re
import time
import praw
import feedparser

from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict
from cloudbot import hook
from cloudbot.event import EventType
from cloudbot.util import database, web, formatting
from sqlalchemy import Table, Column, String, Integer, PrimaryKeyConstraint, desc
from sqlalchemy.sql import select, insert, delete
from sqlalchemy.exc import IntegrityError

t = 'https://www.reddit.com/r/'
subs = defaultdict(list)
last_entry = defaultdict(str)
status = defaultdict(int)

feed_subs = Table(
    'feed_subs',
    database.metadata,
    Column('channel', String(25)),
    Column('subs', String(255)),
    PrimaryKeyConstraint('channel', 'subs')
)

@asyncio.coroutine
#@hook.on_start()
def initial_load(bot, db):
    """ When the script starts, build the url and last_entry the initial feed """
    print("got here")
    global subs, status
    conn = bot.connections['snoonet']
    if conn.ready:
        all_subs = get_all_subs(db)
        if not all_subs:
            return
        for row in all_subs:
            chan = row['channel']
            dbsubs = row['subs'] 
            status[chan] = 1
            subs[chan] = dbsubs.split('+')
            url = '{}{}/new/.rss?sort=new&limit=1'.format(t, dbsubs)
            get_initial_feed(conn, chan, url)

#@asyncio.coroutine
def get_initial_feed(conn, chan, url):
    """ Grab the entries from the feed and last_entry them """
    global last_entry
    feed = feedparser.parse(url)
    if feed and feed.entries:
        last_entry[chan] = get_url_id(feed.entries[0].link)
        conn.message(chan, format_feed(feed.entries[0]))

#@hook.periodic(30, initial_interval=30)
def refresh_feed(bot, db):
    conn = bot.connections['snoonet']
    if conn.ready:
        for chan in subs:
            if status[chan] == 1:
                url = '{}{}/new/.rss?sort=new&before=t3_{}'.format(t, '+'.join(subs[chan]), last_entry[chan])
                update_feed(conn, chan, url)

def update_feed(conn, chan, url):
    """ Update the existing feed last_entry with latest entries """
    global last_entry
    feed = feedparser.parse(url)
    if feed and feed.entries:
        last_entry[chan] = get_url_id(feed.entries[0].link)
        for item in reversed(feed.entries):
            conn.message(chan, format_feed(item))
            time.sleep(3)

#@hook.periodic(60, initial_interval=60)
#def display_feed_item(bot):
#    global feed
#    conn = bot.connections['snoonet']
#    if conn.ready:
#        for chan in subs:
#            if feed.get(chan) and status[chan] == 1:
#                item = feed[chan].pop()
#                display_text = format_feed(item)
#                conn.message(chan, display_text)

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