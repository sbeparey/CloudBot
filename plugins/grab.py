import re
import random

from collections import defaultdict
from sqlalchemy import Table, Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import select
from cloudbot import hook
from cloudbot.util import database

search_pages = defaultdict(list)

table = Table('grab',
    database.metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String),
    Column('time', String),
    Column('quote', String),
    Column('chan', String))

#@hook.on_start()
#def load_cache(db):
#    """
#    :type db: sqlalchemy.orm.Session
#    """
#    global grab_cache
#    grab_cache = {}
#    for row in db.execute(table.select().order_by(table.c.time)):
#        name = row["name"].lower()
#        quote = row["quote"]
#        chan = row["chan"]
#        if chan not in grab_cache:
#            grab_cache.update({chan:{name:[chan]}})
#        elif name not in grab_cache[chan]:
#            grab_cache[chan].update({name:[quote]})
#        else:
#            grab_cache[chan][name].append(quote)

def check_grabs(db, chan, name, msg):
    try:
        grab = get_grab(db, chan, name, msg)
        if grab:
            return True
        else:
            return False
    except:
        return False

def get_grab_by_id(db, id):
   """Gets a grab by its id"""
   if id:
       query = table.select() \
           .where(table.c.id == id)
       return db.execute(query).fetchone()


def get_grab(db, chan, nick, msg):
    if nick and chan and msg:
        query = table.select() \
            .where(table.c.chan == chan) \
            .where(table.c.name == nick.lower()) \
            .where(table.c.quote == msg) \
            .order_by(table.c.time.desc())
        return db.execute(query).fetchone()


def last_grab(db, chan, nick):
    if chan and nick:
        query = table.select() \
            .where(table.c.chan == chan) \
            .where(table.c.name == nick.lower()) \
            .order_by(table.c.time.desc()) \
            .limit(1)
        return db.execute(query).fetchone()


def grab_random(db, chan, nick):
    if nick:
        query = 'select id, time, chan, name, quote from grab where name = :name and chan = :chan group by random() limit 1'
        return db.execute(query, {'name': nick.lower(), 'chan': chan}).fetchone()
    else: 
        query = 'select id, time, chan, name, quote from grab where chan = :chan group by random() limit 1'
        return db.execute(query, {'chan': chan}).fetchone()


def grab_add(conn, db, time, chan, nick, msg):
    # Adds a quote to the grab table
    query = table.insert().values(name=nick.lower(), time=time, quote=msg, chan=chan)
    db.execute(query)
    db.commit()


def delete_grab(db, id):
    if id:
        query = table.delete() \
            .where(table.c.id == id)
        db.execute(query)
        db.commit()

@hook.command()
def grab(text, nick, chan, db, conn):
    """grab <nick> grabs the last message from the
    specified nick and adds it to the quote database"""
    if text.lower() == nick.lower():
        return "Didn't your mother teach you not to grab yourself?"
    
    for item in conn.history[chan].__reversed__():
        name, timestamp, msg = item
        if text.lower() == name.lower():
            # check to see if the quote has been added
            if msg.startswith('.'):
                return "cannot grab a command."

            if check_grabs(db, chan, name, msg):
                return "I already have that quote from \x02{}\x02 in the database".format(text)
                break
            else:
                # the quote is new so add it to the db.
                try:
                    grab_add(conn, db, timestamp, chan, name, msg)
                    grab = get_grab(db, chan, name, msg)
                    if grab:
                        conn.notice(name, "You've been grabbed, you can use \x02.grabdel {}\x02 to delete the grab".format(grab['id']))
                    return "the operation succeeded."
                except:
                    return "sorry, something happened while trying to save the grab into the database."
                #if check_grabs(db, chan, nick, msg):
                #    return "the operation succeeded."
                #break
    return "I couldn't find anything from {} in recent history.".format(text)


@hook.command("lastgrab", "lgrab")
def lastgrab(db, text, chan, message):
    """prints the last grabbed quote from <nick>."""
    lgrab = ""
    try:
        lgrab = last_grab(db, chan, text)
    except:
        return "<\x02{}\x02> has never been grabbed.".format(text)
    if lgrab:
        message(format_grab(lgrab['id'], text, lgrab['quote']),chan)
    else:
        return "<\x02{}\x02> has no grabs.".format(text)


@hook.command("grabrandom", "grabr", autohelp=False)
def grabrandom(db, text, chan, message):
    """grabs a random quote from the grab database"""
    name = ""
    if text:
        tokens = text.split(' ')
        if len(tokens) > 1:
            name = random.choice(tokens)
        else:
            name = tokens[0]
    else:
        try:
            grab = grab_random(db, chan, '')
            if grab:
                message(format_grab(grab['id'], grab['name'], grab['quote']), chan)
                return
        except:
            return "I couldn't find any grabs in {}.".format(chan)
    try:
        grab = grab_random(db, chan, name)
        if grab:
            message(format_grab(grab['id'], name, grab['quote']), chan)
            return
        else:
            return "it appears {} has never been grabbed in {}".format(name, chan)
    except:
        return "it appears {} has never been grabbed in {}".format(name, chan)


@hook.command("grabdel", "delgrab", autohelp=False)
def grabdel(db, chan, nick, text):
    """Deletes a user's grabbed item"""
    if text and text.isdigit():
        grab = get_grab_by_id(db, text)
        if grab and grab['name'] == nick.lower():
            try:
                delete_grab(db, text)
                return "operation successful"
            except:
                return "sorry, something happened while attempting to delete the grab."
        else:
            return "invalid grab id or the grab is not yours to delete"


@hook.command("grabdel2", "delgrab2", permissions=["grabdelete"], autohelp=False)
def grabdel2(db, chan, nick, text):
    """Deletes a given grab by its grab id"""
    if text and text.isdigit():
        try:
            delete_grab(db, text)
            return "operation successful!"
        except:
            return "sorry, something happened while attempting to delete the grab."
    else:
        return "you must provide me with a valid grab id."


def format_grab(id, name, quote):
    # add nonbreaking space to nicks to avoid highlighting people with printed
    # grabs
    name = "{}{}{}".format(name[0], u"\u200B", name[1:])
    if quote.startswith("\x01ACTION") or quote.startswith("*"):
        quote = quote.replace("\x01ACTION", "").replace("\x01", "")
        out = "* \x02{}\x02 {} [{}]".format(name, quote, id)
        return out
    else:
        out = "<\x02{}\x02> {} [{}]".format(name, quote, id)
        return out

#@hook.command("grabsearch", "grabs", autohelp=False)
#def grabsearch(text, chan):
#    """.grabsearch <text> matches "text" against nicks or grab strings in the database"""
#    out = ""
#    result = []
#    search_pages[chan] = []
#    search_pages[chan + "index"] = 0
#    try:
#        quotes = grab_cache[chan][text.lower()]
#        for grab in quotes:
#            result.append((text, grab))
#    except:
#       pass
#    for name in grab_cache[chan]:
#        for grab in grab_cache[chan][name]:
#            if name != text.lower():
#                if text.lower() in grab.lower():
#                    result.append((name, grab))
#    if result:
#        for grab in result:
#            name = grab[0]
#            if text.lower() == name:
#                name = text
#            quote = grab[1]
#            out += "{} {} ".format(format_grab(name, quote), u'\u2022')
#        out = smart_truncate(out)
#        out = out[:-2]
#        out = two_lines(out, chan)
#        if len(search_pages[chan]) > 1:
#            return "{}(page {}/{}) .moregrab".format(out, search_pages[chan + "index"] + 1 , len(search_pages[chan]))
#        return out
#    else:
#        return "I couldn't find any matches for {}.".format(text)

#@hook.command("moregrab", autohelp=False)
#def moregrab(text, chan):
#    """if a grab search has lots of results the results are pagintated. If the most recent search is paginated the pages are stored for retreival. If no argument is given the next page will be returned else a page number can be specified."""
#    if not search_pages[chan]:
#        return "There are grabsearch pages to show."
#    if text:
#        index = ""
#        try:
#            index = int(text)
#        except:
#            return "Please specify an integer value."
#        if abs(int(index)) > len(search_pages[chan]) or index == 0:
#            return "please specify a valid page number between 1 and {}.".format(len(search_pages[chan]))
#        else:
#            return "{}(page {}/{})".format(search_pages[chan][index - 1], index, len(search_pages[chan]))
#    else:
#        search_pages[chan + "index"] += 1
#        if search_pages[chan + "index"] < len(search_pages[chan]):
#            return "{}(page {}/{})".format(search_pages[chan][search_pages[chan + "index"]], search_pages[chan + "index"] + 1, len(search_pages[chan]))
#        else:
#            return "All pages have been shown you can specify a page number or do a new search."


#def two_lines(bigstring, chan):
#    """Receives a string with new lines. Groups the string into a list of strings with up to 3 new lines per string element. Returns first string element then stores the remaining list in search_pages."""
#    global search_pages
#    temp = bigstring.split('\n')
#    for i in range(0, len(temp), 2):
#        search_pages[chan].append('\n'.join(temp[i:i + 2]))
#    search_pages[chan + "index"] = 0
#    return search_pages[chan][0]


#def smart_truncate(content, length=355, suffix='...\n'):
#    if len(content) <= length:
#        return content
#    else:
#        return content[:length].rsplit(' \u2022 ', 1)[0] + suffix + content[:length].rsplit(' \u2022 ', 1)[1] + smart_truncate(content[length:])