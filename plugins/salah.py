import asyncio
import random
import functools

from bs4 import BeautifulSoup
import requests

from cloudbot import hook

# @asyncio.coroutine
@hook.command('magrib',autohelp=False)
def magrib(message):
    """ gets a page of random FMLs and puts them into a dictionary """
    url = 'http://mecca.net/mecca-live-prayers/'
    r = requests.get(url)
    # _func = functools.partial(requests.get, url, timeout=6)
    # request = yield from loop.run_in_executor(None, _func)
    soup = BeautifulSoup(r.text)

    for e in soup.find('td', {'data-label': 'MAGHRIB'}):
    	message(e)