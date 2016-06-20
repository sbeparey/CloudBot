#!/bin/python

from collections import OrderedDict
import requests
import re
import os
import sqlite3


ar_meta = OrderedDict([
	('name'			, 'القرآن الكريم'), 
	('translator'	, ''), 
	('language'		, 'Arabic'), 
	('last_update'	, ''), 
	('source'		, 'Tanzil.net')
])

quran_meta = OrderedDict([
	('ar_arabic_clean'	, ar_meta), 
	('ar_arabic'		, ar_meta)
])
def process_meta(text):
	name = re.findall(r'Name: (.*)', text)[0]
	translator = re.findall(r'Translator: (.*)', text)[0]
	language = re.findall(r'Language: (.*)', text)[0]
	last_update = re.findall(r'Last Update: (.*)', text)[0]
	source = re.findall(r'Source: (.*)', text)[0]
	return OrderedDict([
				('name'			, name), 
				('translator'	, translator), 
				('language'		, language), 
				('last_update'	, last_update), 
				('source'		, source)
			])

session = requests.Session()

clean_params = 	{
	'quranType'	: 'simple-clean', 
	'outType'	: 'txt-2', 
	'agree'		: 'true'
}
enhenced_params = {
	'quranType'	: 'simple-enhanced', 
	'marks'		: 'true', 
	'sajdah'	: 'true', 
	'rub'		: 'true', 
	'alef'		: 'true', 
	'outType'	: 'txt-2', 
	'agree'		: 'true'
}

try:
	print('downloading ar_arabic_clean')
	r = session.get('http://tanzil.net/pub/download/download.php', params=clean_params)
	clean_text = r.text
	print('downloading ar_arabic')
	r = session.get('http://tanzil.net/pub/download/download.php', params=enhenced_params)
	enhenced_text = r.text
	r = session.get('http://tanzil.net/trans/')
	downloads = r.text
except e:
	print(e)
	os._exit(os.EX_PROTOCOL)

urls = re.findall(r'href="(http://tanzil\.net/trans/[^"/]+)"', downloads)
urls.sort()

trans_list = []
translations =OrderedDict()

clean_text = clean_text[:clean_text.index('\r\n\r\n')]
enhenced_text = enhenced_text[:enhenced_text.index('\r\n\r\n')]
translations['ar_arabic_clean'] = clean_text
translations['ar_arabic'] = enhenced_text

for url in urls:
	#print(url)
	trans = re.sub(r'[\.-]', '_', url.split('/')[-1])
	trans_list.append(trans)

	try:
		print('downloading', url)
		trans_text = session.get(url).text
	except:
		print('failed to get', url)
		os._exit(os.EX_PROTOCOL)

	split_pos = trans_text.index('\n\n')
	meta_text = trans_text[split_pos:]
	trans_text = trans_text[:split_pos]
	meta = process_meta(meta_text)

	# print erroneous lines and fix them, report to tanzil.net
	if '\u0085' in trans_text:
		print('{}: {}\n'.format(trans, re.findall(r'\n(.*\u0085.*)\n', trans_text)))
		trans_text = trans_text.replace('\u0085', '')
	translations[trans] = trans_text
	quran_meta[trans] = meta

session.close()

# this will result in trans_list = ['ar_arabic', 'ar_arabic_clean', ...]
trans_list.insert(0, 'ar_arabic_clean')
trans_list.insert(0, 'ar_arabic')
print(trans_list)
print(quran_meta)

keep_once = True
big_text = []
for trans in trans_list:
	print('processing ', trans)
	lines = translations[trans].splitlines()
	for line in lines:
		_id = lines.index(line)
		if keep_once:
			params = line.split('|')
			params[0] = int(params[0])
			params[1] = int(params[1])
			params.insert(0, _id+1)
			big_text.append(params)
		else:
			big_text[_id].append(line.split('|')[2])
	keep_once = False


conn = sqlite3.connect('quran.db')
cur = conn.cursor()
# construct the create table query
query = 'CREATE TABLE Quran (id integer primary key autoincrement, surah integer, ayah integer'
for col in trans_list: query += ', {} text'.format(col)
query += ')'
cur.execute(query)

# construct the insert values query
query = 'INSERT INTO Quran VALUES(?,?,?{})'.format(',?'*len(trans_list))
cur.executemany(query, big_text)

query = 'CREATE VIRTUAL TABLE QuranFTS USING fts5 (surah, ayah'
for col in trans_list: query += ', {}'.format(col)
query += ', content="Quran", content_rowid="id", tokenize="unicode61 remove_diacritics 0")'
cur.execute(query)
cur.execute("INSERT INTO QuranFTS(QuranFTS) VALUES('rebuild')")
cur.execute("INSERT INTO QuranFTS(QuranFTS) VALUES('optimize')")

conn.commit()
conn.close()
