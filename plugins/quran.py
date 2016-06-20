import os.path
import re
import shelve
import random
import apsw

from cloudbot import hook
from .quranmeta import *

helpText = '''\
@C@quran @P@<suran> <ayah> [<last_ayah>]@P@@C@: show the ayah number @P@ayah@P@ \
from the given surah number @P@surah@P@, optionally, if @P@ayah_last@P@ is given, \
the next ayaat will be shown till the last ayah number @P@last_ayah@P@ is reached.\

@C@quran prev @P@[<translation_code>]@P@@C@: show the previous ayah, optionally in the given \
translation @P@translation_code@P@\

@C@quran last @P@[<translation_code>]@P@@C@: show the last ayah, optionally in the given \
translation @P@translation_code@P@\

@C@quran next @P@[<translation_code>]@P@@C@: show the next ayah, optionally in the given \
translation @P@translation_code@P@\

@C@quran random @P@[<translation_code>]@P@@C@: show a random ayah, optionally in the given \
translation @P@translation_code@P@\

@C@quran search @P@[<translation_code>] <terms>@P@@C@: seach for @P@terms@P@ in the \
given translation @P@translation_code@P@ or in the default translation set by the \
"@C@quran set translation@C@" command.\

@C@quran show@C@: show search results, three at a time.\

@C@quran trans[lation[s]] @P@[<s>]@P@@C@: show a list of translations codes, if @P@s@P@ is given, \
how infomations about the given translations codes starting with the string @P@s@P@.\

@C@quran set trans[lation] @P@<translation_code>@P@@C@: set the default translation \
for the current context to the translation @P@translation_code@P@'''

# color scheme
BACKGROUND_COLOR  = '01' # black
FOREGROUND_COLOR  = '15' # light grey
HEADER_BG_COLOR   = '06' # purple
HEADER_FG_COLOR   = '00' # white

CONTROL_COLOR     = '\x03'
CONTROL_BOLD      = '\x02'
CONTROL_UNDERLINE = '\x1f'
CONTROL_INVERT    = '\x16'
CONTROL_ITALIC    = '\x1d'

def bold(s):
    return CONTROL_BOLD + s + CONTROL_BOLD
def invert(s):
    return CONTROL_INVERT + s + CONTROL_INVERT
def italicize(s):
    return CONTROL_ITALIC + s + CONTROL_ITALIC

def header(s):
    return bold(CONTROL_COLOR+HEADER_FG_COLOR+','+HEADER_BG_COLOR + ' ' + s + ' ' + CONTROL_COLOR)
def body(s):
    return CONTROL_COLOR+FOREGROUND_COLOR+','+BACKGROUND_COLOR + s + CONTROL_COLOR
def footer(s):
    return header(s)

@hook.on_start()
def setup(bot):
    global conn
    global persist_path
    persist_path = os.path.join(bot.data_dir, 'persist')

    try:
        conn = apsw.Connection(os.path.join(bot.data_dir, 'quran.db'), apsw.SQLITE_OPEN_READONLY)
        #conn = sqlite3.connect('quran.db')
    except apsw.Error as e:
        print('setup()', e)
    if not conn:
        raise ValueError("Quran Database Error.")
    print('Connected to DB')
    global c
    c = conn.cursor()

def shutdown():
    c.close()
    conn.close()
    print('Connection closed')


def getTransInfo(trans):
    _trans = TransInfo[trans]
    return _trans['language'] + ' (' + _trans['name'] + ') ' + _trans['translator']


def getSurahInfo(surah):
    data = MetaData[surah]
    return('{:s} ({:s}) {:s}, Surah #{:d}: {:d} Ayaat, Chronological Order: {:d}, {:s}'.format(
            data[5], data[4], data[6], surah, data[1], data[2], data[7]))


def getAyahText(surah, ayah, last, trans):
    #conn = sqlite3.connect(os.path.dirname(__file__) + '/quran.db')
    try:
        c.execute('select {:s} from Quran where surah={:d} and ayah between {:d} and {:d}'.format(
            ','.join(trans), surah, ayah, last))
        ayahText = c.fetchall()
    except apsw.Error as e:
        print('getAyahText:', e)
        return None
    return ayahText


def getSearchResult(text, trans):
    #conn = sqlite3.connect(os.path.dirname(__file__) + '/quran.db')
    try:
        result = [r for r in c.execute('select surah, ayah from QuranFTS where QuranFTS match \'{:s}: {:s}\''.format(trans, text))]
    except apsw.Error as e:
        print('getSearchResult({}, {}):'.format(text, trans), e)
        return None
    return result

def roundUpDiv(num, den, _min):
    sz = num / den
    return int(sz) + (1 if int(sz - int(sz) > _min) else 0)


MAX_TEXT_LENGTH = 400
def ircNormalizeText(text, sep=' '):
    encoded = text.encode()
    if len(encoded) <= MAX_TEXT_LENGTH:
        return [text]

    maxlen = roundUpDiv(MAX_TEXT_LENGTH, roundUpDiv(len(encoded), len(text), 0.03), 0)

    if sep == ' ':
        keepsep = 0
    else:
        keepsep = 1

    _text = []
    while len(text) > maxlen:
        pos = text.rfind(sep, 0, maxlen)
        if pos == -1:
            pos == maxlen
        _text.append(text[:pos+keepsep])
        text = text[pos+1:]
    if len(text) > 0:
        _text.append(text)

    return _text


def htmltoirc(ayahText):
    ayahText = re.sub('</?[uU]>', CONTROL_UNDERLINE, ayahText)
    ayahText = re.sub('</?[bB]>', CONTROL_BOLD, ayahText)
    return ayahText


def getNormalizedAyah(surah, ayah, last, trans):
    if surah is None or ayah is None:
        return None

    _ayahList = getAyahText(surah, ayah, last, trans)
    if _ayahList is None:
        return None

    ayahList = []
    for _ayah in _ayahList:
        ayahTransList = []
        for _trans in trans:
            ayahText = _ayah[trans.index(_trans)]
            if _trans == 'en_transliteration':
                ayahText = htmltoirc(ayahText)
            if 'zh' in _trans or 'ja' in _trans:
                sep = b'\xef\xbc\x8c'.decode()
            else:
                sep = ' '
            ayahTransList.append(ircNormalizeText(ayahText, sep))
        ayahList.append([str(ayah + _ayahList.index(_ayah)), ayahTransList])
    return ayahList


def validateArgs(chan, surah, ayah, last, trans):
    if surah is None:
        return (None, None, None, None)

    surah = int(surah)
    if surah < 1 or surah > 114:
        return (None, None, None, None)

    if ayah is None:
        return (surah, None, None, None)

    ayah = int(ayah)
    if ayah < 1 or ayah > MetaData[surah][1]:
        return (surah, None, None, None)

    transList = []
    for _trans in trans:
        if _trans in Trans or _trans in TransAlias:
            transList.append(_trans)
    trans = transList
    for _trans in trans:
        if _trans in TransAlias:
            trans[trans.index(_trans)] = TransAlias[_trans]

    if len(trans) == 0:
        try:
            with shelve.open(persist_path) as persist:
                trans = [persist[chan+'_trans']]
        except:
            trans = ['en_sahih']

    if last is None:
        last = ayah
        return (surah, ayah, last, trans)

    last = int(last)
    if last <= ayah or last > MetaData[surah][1]:
        last = ayah
        return (surah, ayah, last, trans)

    if (last - ayah) > 6:
        last = ayah + 6

    return (surah, ayah, last, trans)

@hook.regex(r'[Qq]uran\s+(?!prev)(?!last)(?!next)(?!random)(?!set)(?!trans)(?!search)(?!show)(?!help)(.*)')
def quranAyah(match, chan, message):
    args = re.sub('[.:-]', ' ', match.group(1))

    transList = re.findall('(\w+)', re.sub('\S*\d+\S*', '', args))

    args = re.search('(\d+)\s*(\d+)?\s*(\d+)?', args)
    if args is None:
        return
    args = args.groups()

    args = validateArgs(chan, args[0], args[1], args[2], transList)
    if args[2] is not None:
        with shelve.open(persist_path) as persist:
            persist[chan+'_last'] = (args[0], args[2])
    prettyPrint(message, *args)

@hook.regex(r'[Qq]uran\s+prev\s*(.*)')
def quranPrev(match, chan, message):
    transList = re.findall('(\w+)', re.sub('\S*\d+\S*', '', match.group(1)))
    try:
        with shelve.open(persist_path) as persist:
            surah = persist[chan+'_last'][0]
            ayah = persist[chan+'_last'][1] - 1
    except:
        return

    if ayah == 0:
        if surah == 1:
            surah = 114
        else:
            surah -= 1
        ayah = MetaData[surah][1]

    args = validateArgs(chan, surah, ayah, None, transList)
    with shelve.open(persist_path) as persist:
        persist[chan+'_last'] = (args[0], args[2])
    prettyPrint(message, *args, linear=True)


@hook.regex(r'[Qq]uran\s+last\s*(.*)')
def quranLast(match, chan, message):
    transList = re.findall('(\w+)', re.sub('\S*\d+\S*', '', match.group(1)))
    try:
        with shelve.open(persist_path) as persist:
            surah = persist[chan+'_last'][0]
            ayah = persist[chan+'_last'][1]
    except:
        return
    args = validateArgs(chan, surah, ayah, None, transList)
    prettyPrint(message, *args, linear=True)


@hook.regex(r'[Qq]uran\s+next\s*(.*)')
def quranNext(match, chan, message):
    transList = re.findall('(\w+)', re.sub('\S*\d+\S*', '', match.group(1)))
    try:
        with shelve.open(persist_path) as persist:
            surah = persist[chan+'_last'][0]
            ayah = persist[chan+'_last'][1] + 1
    except:
        return

    if ayah > MetaData[surah][1]:
        if surah == 114:
            surah = 1
        else:
            surah += 1
        ayah = 1

    args = validateArgs(chan, surah, ayah, None, transList)
    with shelve.open(persist_path) as persist:
        persist[chan+'_last'] = (args[0], args[2])
    prettyPrint(message, *args, linear=True)


@hook.regex(r'[Qq]uran\s+random\s*(.*)')
def quranRandom(match, chan, message):
    transList = re.findall('(\w+)', re.sub('\S*\d+\S*', '', match.group(1)))
    _id = random.randint(1, 6236)
    try:
        surah, ayah = c.execute('select surah, ayah from Quran where id={:d}'.format(_id)).fetchone()
    except:
        return

    args = validateArgs(chan, surah, ayah, None, transList)
    with shelve.open(persist_path) as persist:
        persist[chan+'_last'] = (args[0], args[2])
    prettyPrint(message, *args, linear=True)


@hook.regex(r'[Qq]uran\s+set\s+trans(?:lation)?\s+(\w+)\s*$')
def quranSetTrans(match, chan, message):
    trans = match.group(1)
    if trans in Trans:
        with shelve.open(persist_path) as persist:
            persist[chan+'_trans'] = trans
        return
    if trans in TransAlias:
        with shelve.open(persist_path) as persist:
            persist[chan+'_trans'] = TransAlias[trans]
        return
    message('No such translation. Type "quran trans" for a list of translations.')


@hook.regex(r'[Qq]uran\s+trans(?:lations?)?\s*$')
def quranTrans(notice):
    notice(header('Available Translations Codes:'))
    for line in ircNormalizeText(' '.join(Trans)):
        notice(line)
    notice(footer('Type "quran trans <code>" to learn more about each translation.'))


@hook.regex(r'[Qq]uran\s+trans(?:lations?)?\s+(\w+)\s*$')
def quranTransInfo(match, notice):
    for trans in Trans:
        if re.match(match.group(1), trans):
            notice(body(' ') + header(trans) + body(' ' + getTransInfo(trans) + ' '))


@hook.regex(r'[Qq]uran\s+search\s+(.*)\s*$')
def quranSearch(match, chan, message):
    args = re.split('\s+', match.group(1).strip())

    if args[0] == 'ar':
        del args[0]
        trans = 'ar_arabic_clean'
    elif args[0] in TransAlias:
        trans = TransAlias[args[0]]
        del args[0]
    elif args[0] in Trans:
        trans = args.pop(0)
    else:
        try:
            with shelve.open(persist_path) as persist:
                trans = persist[chan+'_trans']
            if trans == 'ar_arabic':
                trans = 'ar_arabic_clean'
        except:
            trans = 'en_sahih'

    terms = ' '.join(args)

    import time
    start = time.time()
    result = getSearchResult(terms, trans)
    _time = time.time() - start
    if result is None:
        #message('Database Error!')
        return

    message('Found {:d} matches for \'{:s}\' in {:s} ({:f} sec.)'.format(len(result), terms, trans, _time))

    with shelve.open(persist_path) as persist:
        persist[chan+'_result'] = [result, trans if (trans != 'ar_arabic_clean') else 'ar_arabic']

    if len(result) > 0 and len(result) <= 80:
        for _result in prettifySearch(result):
            message(_result)
    else:
        message('Please refine your search query.')


@hook.regex(r'[Qq]uran\s+show\s*$')
def quranSearchShow(chan, message):
    try:
        with shelve.open(persist_path) as persist:
            result = persist[chan+'_result'][0]
            trans = persist[chan+'_result'][1]
    except:
        message('No results to show.')
        return

    ayahText = ''
    for i in range(len(result)):
        if i > 2:
            break
        surah, ayah = result.pop(0)
        prettyPrint(message, surah, ayah, ayah, [trans], True)

    with shelve.open(persist_path) as persist:
        persist[chan+'_result'] = [result, trans]
        if len(result) == 0:
            del persist[chan+'_result']



def prettifySearch(result):
    _result = ''
    surah = 0
    for pair in result:
        if surah == pair[0]:
            _result+=','+str(pair[1])
        else:
            _result+='|'+bold(str(pair[0]))+':'+str(pair[1])
        surah = pair[0]
    return ircNormalizeText(_result[1:], '|')

def prettyPrint(message, surah, ayah, last, trans, linear=False):
    if surah is None:
        message(header(' 114 Surah in the Quran '))
        return

    if ayah is None:
        message(header(getSurahInfo(surah)))
        return

    ayahList = getNormalizedAyah(surah, ayah, last, trans)
    if ayahList is None:
        message('Database Error!')
        return

    if not linear:
        message(header(getSurahInfo(surah)))
    for _ayah in ayahList:
        for ayahTrans in _ayah[1]:
            firstLine = True
            for ayahText in ayahTrans:
                if firstLine:
                    _ayahText = ('' if not linear else 
                                header('{:d}.{:s} ({:s})'.format(surah, MetaData[surah][5], MetaData[surah][4]))) + \
                                body(' ' + bold(_ayah[0] + ':')) + body(' ' + ayahText + ' ')
                    firstLine = False
                else:
                    _ayahText = body(' ' + ayahText + ' ')
                message(_ayahText)
    if not linear:
        message(footer(getTransInfo(trans[0]) if (len(trans) == 1) else 'Type "quran trans" for more information.'))

@hook.regex(r'[Qq]uran\s+help\s*$')
def quranHelp(notice):
    BODY_COLOR = CONTROL_COLOR+FOREGROUND_COLOR+','+BACKGROUND_COLOR
    COMMAND_COLOR = CONTROL_COLOR+'00'
    PARAM_COLOR = CONTROL_COLOR+'06'

    def hCommand(m):
        return COMMAND_COLOR + bold(m.group(1)) + BODY_COLOR
    def hParameter(m):
        return PARAM_COLOR + italicize(m.group(1)) + BODY_COLOR
    def say(s):
        s = re.sub('@C@(.*?)@C@', hCommand, s)
        s = re.sub('@P@(.*?)@P@', hParameter, s)
        notice(BODY_COLOR + ' ' + s + ' ')

    notice(header('Quran Commands Help List'))

    for text in helpText.splitlines():
        say(text)
