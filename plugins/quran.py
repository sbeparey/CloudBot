#=====================================================================
#
#  Quran Api
#  Author: sy @ irc.snoonet.org 
#  Channel: #Islam
#  Last Update: November 22, 2015
#  Qur'an and the translations provided by: Tanzil.net
#
#=====================================================================

import re
import inspect
import time

from cloudbot import hook
from cloudbot.util import database

quran_text = Table(
    'quran_text',
    database.metadata,
    Column('id', Integer),
    Column('sura', Integer),
    Column('aya', Integer),
    Column('text', String),
    PrimaryKeyConstraint('id')
    )

quran_url = re.compile('^((http|https):\/\/)?((legacy|www)\.)?quran\.com/([1-9]|[1-9][0-9]|10[0-9]|11[0-4])(/([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-7][0-9]|28[0-6])((\-)([1-9]|[1-9][0-9]|1[0-9][0-9]|2[0-7][0-9]|28[0-6]))?)?$', re.IGNORECASE)

@hook.regex(quran_url)
def quran_url(match, chan, message, db):
    url_array = str(match.group()).replace('://', '').split('/')
    url_array.pop(0)
    text = '/'.join(url_array)
    return quran(text, message, db)

# @hook.periodic(15, initial_interval=15)
# def recite_sura(db):
#     """Recites the given sura"""
#     global recite_aya
#     return recite
#     if recite:
#         query = db.execute("select sura, aya, text from {} where sura = :sura and aya = :aya".format(recite_table), { 'sura': recite_sura, 'aya': recite_aya}).fetchone()
#         if query is None:
#             return "\x02{}.{}\x02 does not exist. If you think this is an error, please let us know".format(recite_sura, recite_aya)
#             row = "\x02{}.{}:\x02 {} ".format(query[0], query[1], query[2])
#             result = smart_truncate(row)
#             if recite_aya < recite_max_aya:
#                 recite_aya = recite_aya + 1
#             else:
#                 recite_aya = 1
#             return result

@hook.command('recite', 'iqra', 'iqraa', autohelp=False)
def recite(text, message, db):
    """Automatically recites a given surah"""
    recite = True
    table = 'quran_sahih'

    params = text.strip().split()

    l = len(params)
    if l == 1:
        p = params[0]
        if p.lower() == 'stop':
            recite = False
        else:
            try:
                sura = int(params[0])
                if sura < 1:
                    return "You have to start somewhere, try .quran 1:1"
                elif sura > 114:
                    return "There are only 114 suwar/chapters in the Qur'an"
            except ValueError:
                return "You have to give me a sura/chapter number. Use format <sura>:<ayah> e.g., 55:13"
        
            query = db.execute("select max(aya) from quran_sahih where sura = :sura".format(table), {'sura': sura}).fetchone()
            max_aya = int(query[0])        
            aya = 1

        while recite and aya <= max_aya:
            query = db.execute("select sura, aya, text from {} where sura = :sura and aya = :aya".format(table), { 'sura': sura, 'aya': aya}).fetchone()
            if query is None:
                return "\x02{}.{}\x02 does not exist. If you think this is an error, please let us know".format(sura, aya)
            row = "\x02{}.{}:\x02 {} ".format(query[0], query[1], query[2])
            result = smart_truncate(row)
            if aya < max_aya:
                aya = aya + 1
            else:
                aya = 1
            message(result)
            time.sleep(15)

@hook.periodic(15, initial_interval=15)
def recite_sura(db):
    sura = 1
    aya = 1
    max_aya = 7
    query = db.execute("select sura, aya, text from {} where sura = :sura and aya = :aya".format(table), { 'sura': sura, 'aya': aya}).fetchone()
    if query is None:
        return "\x02{}.{}\x02 does not exist. If you think this is an error, please let us know".format(sura, aya)
    row = "\x02{}.{}:\x02 {} ".format(query[0], query[1], query[2])
    result = smart_truncate(row)
    if aya < max_aya:
        aya = aya + 1
    else:
        aya = 1
    message(result)

@hook.command('q', 'quran', autohelp=False)
def quran(text, message, db):
    """Prints the specified Qur'anic verse(s). Default is set to Sahih International version of the Qur'an. Use format <sura>:<starting>-<ending> ayah e.g., 96:1-5. Suffix the command with 'ar' for Arabic script. (May not display properly on all clients)"""
    params = text.strip().split()
    table = 'quran_sahih'
    
    curframe = inspect.currentframe()
    calframe = inspect.getouterframes(curframe, 2)
    url_regex = True if str(calframe[1][3]).lower() == 'quran_url' else False
    
    l = len(params)
    if l == 0:
        return random_verse(db, table)

    verse = split(';:,./', params[0])

    if l == 1 and len(verse) == 1 and verse[0] == 'ar' or verse[0] == 'arabic':
        return random_verse(db, 'quran_text')

    if l > 1:
        arg = params[1].lower()
        if arg == 'ar' or arg == 'arabic':
            table = 'quran_text'
        if arg == 'ali' or arg == 'yusuf ali':
            table = 'quran_ali'
        if arg == 'sahih' or arg == 'saheeh' or arg == 'international':
            table = 'quran_sahih'

    try:
        sura = int(verse[0])
    except ValueError:
        return "You have to give me a sura/chapter number. Use format <sura>:<ayah> e.g., 55:13"
    if sura < 1:
        return "You have to start somewhere, try .quran 1:1"
    elif sura > 114:
        return "There are only 114 suwar/chapters in the Qur'an"
        
    if len(verse) > 2:
        return "Ayat/verses range not understood. Use format <sura>:<starting>-<ending> ayah e.g., 2:255"
    elif len(verse) == 2:
        ayat = split('-', verse[1])
            
        if len(ayat) > 2:
            return "Ayat/verses range not understood. Use format <sura>:<starting>-<ending> ayah e.g., 96:1-5"
        elif len(ayat) == 2:
            try:
                first = int(ayat[0])
                second = int(ayat[1])
                if first < 1 or second < 1:
                    return "Try starting from aya/verse 1"
                elif first > 286 or second > 286:
                    return "Did you know the longest sura/chapter in the Qur'an is the second chapter or Sura Al-Baqarah? It's 286 ayat/verses long. That's as far as I go"
                if first > second:
                    return "I think you have this backward"
                if second - first > 2:
                    if not url_regex:
                        return("http://legacy.quran.com/{}/{}-{}".format(sura, first, second))
                else:
                    query = db.execute("select sura, aya, text from {} where sura = :sura and aya between :first and :second".format(table), { 'sura': sura, 'first': first, 'second': second}).fetchall()
                    if query is None:
                        return "\x02{}.{}-{}\x02 does not exist. If you think this is an error, please let us know".format(sura, first, second)
                    rows = ''
                    for row in query:
                        rows += "\x02{}.{}:\x02 {} ".format(row[0], row[1], row[2])
                    result = smart_truncate(rows)
                    first = query[0][1]
                    second = query[-1][1]
                    if not url_regex:
                        if second > first:
                            result += '\nhttp://legacy.quran.com/{}/{}-{}'.format(sura, first, second)
                        else:
                            result += '\nhttp://legacy.quran.com/{}/{}'.format(sura, first)
                    return(result)
            except ValueError:
                return "You have to give me ayah/verse number. Use format <sura>:<starting>-<ending> e.g., 108:1-3"
        else:
            try:
                aya = int(ayat[0])
                if aya < 1:
                    return "Try starting from aya/verse 1"
                elif aya > 286:
                    return "Did you know the longest sura/chapter in the Qur'an is the second chapter or Sura Al-Baqarah? It's 286 ayat/verses long. That's as far as I go"
                query = db.execute("select sura, aya, text from {} where sura = :sura and aya = :aya".format(table), { 'sura': sura, 'aya': aya}).fetchone()
                if query is None:
                    return "\x02{}.{}\x02 does not exist. If you think this is an error, please let us know".format(sura, aya)
                row = "\x02{}.{}:\x02 {} ".format(query[0], query[1], query[2])
                result = smart_truncate(row)
                if not url_regex:
                    result += '\nhttp://legacy.quran.com/{}/{}'.format(sura, aya)
                return(result)
            except ValueError:
                return "You have to give me ayah/verse number. Use format <sura>:<ayah> e.g., 112:4"
    else:
        if sura == 1 or sura > 96 and sura < 115:
            query = db.execute("select sura, aya, text from {} where sura = :sura".format(table), { 'sura': sura}).fetchall()
            if query is None:
                return "Sura/Chapter \x02{}\x02 does not exist. If you think this is an error, please let us know".format(sura)
            rows = ''
            for row in query:
                rows += "\x02{}.{}:\x02 {} ".format(row[0], row[1], row[2])            
            result = smart_truncate(rows)
            if not url_regex:
                result += '\nhttp://legacy.quran.com/{}'.format(sura)
            return(result)
        else:
            if not url_regex:
                return 'http://legacy.quran.com/{}'.format(sura)

def random_verse(db, table):
    query = db.execute("select sura, aya, text from {} group by random() limit 1".format(table)).fetchone()
    row = "\x02{}.{}:\x02 {} ".format(query[0], query[1], query[2])
    result = smart_truncate(row)
    result += '\nhttp://legacy.quran.com/{}/{}'.format(query[0], query[1])
    return(result)

# def sura_check(sura):
#     try:
#         value = int(sura)
#     except ValueError:
#         return "You have to give me a sura/chapter number. Use format <sura>:<ayah> e.g., 55:13"
#     if value < 1:
#         return "You have to start somewhere, try .quran 1:1"
#     elif value > 114:
#         return "There are only 114 suwar/chapters in the Qur'an"
                
def split(delimiters, string, maxsplit=0):
    pattern = '|'.join(map(re.escape, delimiters))
    return re.split(pattern, string, maxsplit)
    
def smart_truncate(content, length=425, suffix='...\n'):
    if len(content) <= length:
        return content
    else:
        return content[:length].rsplit(' ', 1)[0]+ suffix + content[:length].rsplit(' ', 1)[1] + smart_truncate(content[length:])