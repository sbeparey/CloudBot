import os
import codecs
import random
import asyncio

from cloudbot import hook

opt_out = ['#islam', '#islam2', '#islamadmins', '#quran', '#sy']

@hook.on_start()
def load_fortunes(bot):
    path = os.path.join(bot.data_dir, "fortunes.txt")
    global fortunes
    with codecs.open(path, encoding="utf-8") as f:
        fortunes = [line.strip() for line in f.readlines() if not line.startswith("//")]


@asyncio.coroutine
@hook.command(autohelp=False)
def fortune(chan):
    """- hands out a fortune cookie"""
	
    if chan in opt_out:
        return chan + " does not allow foretelling of fortunes. Work hard and make your own fortunes!"
	
    return random.choice(fortunes)