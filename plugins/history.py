from collections import deque
import time
import asyncio
import re

from cloudbot import hook
from cloudbot.util import timeformat
from cloudbot.event import EventType

db_ready = []


def db_init(db, conn_name):
    """check to see that our db has the the seen table (connection name is for caching the result per connection)
    :type db: sqlalchemy.orm.Session
    """
    global db_ready
    if db_ready.count(conn_name) < 1:
        db.execute("create table if not exists history(time, host, chan, type, nick, message, primary key(time))")
        db.execute("create table if not exists history2(time, host, chan, type, nick, message, primary key(time))")
        db.commit()
        db_ready.append(conn_name)

def track_login(event, db, conn):
    """ Tracks messages for the .seen command
    :type event: cloudbot.event.Event
    :type db: sqlalchemy.orm.Session
    :type conn: cloudbot.client.Client
    """

    db_init(db, conn)

    if event.type is EventType.join:
        type = 'join'
    elif event.type is EventType.part:
        type = 'part'
    elif event.type is EventType.quit:
        type = 'quit'
    elif event.type is EventType.kick:
        type = 'kick'

    message = ''
    if event.content:
        message = event.content

    if event.type is EventType.join or \
       event.type is EventType.part or \
       event.type is EventType.quit or \
       event.type is EventType.kick:
        db.execute("insert or replace into history2(time, host, chan, type, nick, message) values(:time,:host,:chan,:type,:nick,:message)",
            {'time': time.time(), 'host': event.mask, 'chan': event.chan, 'type': type, 'nick': event.nick.lower(), 'message': message})
        db.commit()

def track_seen(event, db, conn):
    """ Tracks messages for the .seen command
    :type event: cloudbot.event.Event
    :type db: sqlalchemy.orm.Session
    :type conn: cloudbot.client.Client
    """

    db_init(db, conn)

    if event.type is EventType.action:
        type = 'action'
    else:
        type = 'message'

    # keep private messages private
    if event.chan[:1] == "#" and not re.findall('^s/.*/.*/$', event.content.lower()):
        db.execute('insert or replace into history(time, host, chan, type, nick, message) values(:time,:host,:chan,:type,:nick,:message)', 
            {'time': time.time(), 'host': event.mask, 'chan': event.chan, 'type': type, 'nick': event.nick.lower(), 'message': event.content})
        db.commit()


def track_history(event, message_time, conn):
    """
    :type event: cloudbot.event.Event
    :type conn: cloudbot.client.Client
    """
    try:
        history = conn.history[event.chan]
    except KeyError:
        conn.history[event.chan] = deque(maxlen=100)
        # what are we doing here really
        # really really
        history = conn.history[event.chan]

    data = (event.nick, message_time, event.content)
    history.append(data)


@hook.event([EventType.join, EventType.message, EventType.action, EventType.part, EventType.quit], singlethread=True)
def chat_tracker(event, db, conn):
    """
    :type db: sqlalchemy.orm.Session
    :type event: cloudbot.event.Event
    :type conn: cloudbot.client.Client
    """
    if event.type is EventType.action:
        event.content = "\x01ACTION {}\x01".format(event.content)

    message_time = time.time()

    if event.type is EventType.join or \
       event.type is EventType.part or \
       event.type is EventType.quit or \
       event.type is EventType.kick:
        track_login(event, db, conn)
    else:
        track_seen(event, db, conn)
    track_history(event, message_time, conn)


@asyncio.coroutine
@hook.command(autohelp=False, permissions=["op"])
def resethistory(event, conn):
    """- resets chat history for the current channel
    :type event: cloudbot.event.Event
    :type conn: cloudbot.client.Client
    """
    try:
        conn.history[event.chan].clear()
        return "Reset chat history for current channel."
    except KeyError:
        # wat
        return "There is no history for this channel."


@hook.command()
def seen(text, nick, chan, db, event, conn):
    """<nick> <channel> - tells when a nickname was last in active in one of my channels
    :type db: sqlalchemy.orm.Session
    :type event: cloudbot.event.Event
    :type conn: cloudbot.client.Client
    """

    if event.conn.nick.lower() == text.lower():
        return "You need to get your eyes checked."

    if text.lower() == nick.lower():
        return "Have you looked in a mirror lately?"

    if not re.match("^[A-Za-z0-9_|\^\`.\-\]\[\{\}\\\\]*$", text.lower()):
        return "I can't look up that name, its impossible to use!"

    db_init(db, conn.name)

    if '_' not in text:
        last_seen = db.execute("select time, type, nick, message from history where nick like :nick and chan = :chan", {'nick': text, 'chan': chan}).fetchall()
    else:
        last_seen = db.execute("select time, type, nick, message from history where nick like :nick escape :escape and chan = :chan", {'nick': text.replace('_', '\_'), 'chan': chan, 'escape': '\\'}).fetchall()

    if last_seen:
        msg = ''
        for row in last_seen:
            if row[2] != text.lower():  # for glob matching
                text = row[2]
            reltime = timeformat.time_since(row[0])
            #if row[1] is 'join':
            #    msg += '{} last joined {} ago. '.format(text, reltime)
            if row[1] == 'message':
                if row[3][0:1] == "\x01":
                    msg += '{} was last seen {} ago: * {} {}. '.format(text, reltime, text, row[3][8:-1])
                else:
                    msg += '{} was last seen {} ago saying: {}. '.format(text, reltime, row[3])
            #if row[1] is 'part':
            #    msg += '{} last parted {} ago saying {}. '.format(text, reltime, row[3])
            #elif row[1] is 'quit':
            #    msg += '{} last quit {} ago saying {}. '.format(text, reltime, row[3])
        if msg != '':
            return msg
    else:
        return "I've never seen {} talking in this channel.".format(text)