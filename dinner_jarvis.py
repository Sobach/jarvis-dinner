#!/usr/bin/python
# -*- coding: utf-8 -*-
# MSK.PULSE backend
from telegram import Emoji, ForceReply, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardHide, TelegramError
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
import logging
from time import sleep
from datetime import datetime, timedelta
import random
from StringIO import StringIO
from csv import reader
from requests import get
import bs4
import re

from settings import TOKEN, CHAT, CALEND
TEXTS = {
	'mealtime': [u'Еда стынет. Пора собираться.', u'Ну чо сидим? Пора бежать.', u'Ай-да пожрать!'],
	'aubergine': [u'Мальчик!!!!! Ты - долбоеб!!!! Сначала идет - томат!!!', u'А я фея без хуя, пейте сок "моя семья"!'],
	'already_counted':[u'Да я понял, понял. Уймись уже.', u'зИнАю!', u'УЗБАГОЙСЯ!!!'],
	'changing_opinion':[u'Как вы, право, непостоянны...'],
	'first_count':[u'Ok!', u'Roger that!'],
	'anekdot':[u'Настало время удивительных историй...', u'Что-то вы какие-то унылые.', u'Держите свежий анекдот.', u'Ребзя, приколитесь:'],
	'wrong_time':[u'Не время сейчас о еде думать!', u'Займись-ка лучше делом.', u'Сколько можно жрать?'],
}
KEYBOARD = InlineKeyboardMarkup(
	[[InlineKeyboardButton(Emoji.HAMBURGER.decode('utf-8')+u' Иду', callback_data='meal.go'),
	InlineKeyboardButton(Emoji.SPEAK_NO_EVIL_MONKEY.decode('utf-8')+u' Пропускаю', callback_data='meal.pass')],
	[InlineKeyboardButton(Emoji.AUBERGINE.decode('utf-8')+u' Я баклажан', callback_data='meal.aubergine'),
	]])
CONTEXT = {}

# MSK_TIME - 3 hrs
DINNER_TIME = (9,0)
WORKING_HOURS = (6,14)

logging.basicConfig(level=logging.ERROR, format=u'[%(asctime)s] LINE: #%(lineno)d | %(levelname)-8s | %(message)s')

updater = Updater(token=TOKEN)
dispatcher = updater.dispatcher

def holidays():
	hd = {}
	si = StringIO(CALEND)
	cr = reader(si, delimiter = ',')
	for row in cr:
		hd[int(row[0])] = {k:set([int(x) for x in v.split(',')]) for k, v in zip(range(1,13), row[1:13])}
	return hd

def strip_tags(html):
	soup = bs4.BeautifulSoup('<tree>'+html+'</tree>')
	for tag in soup.findAll(True):
		tag.append(' ')
		tag.replaceWithChildren()
	result = unicode(soup)
	result = re.sub(' +', ' ', result, flags=re.UNICODE)
	result = re.sub(r' ([\.,;:?!])', r'\1', result, flags=re.UNICODE)
	return result.strip()

def strip_spaces(text):
	text = re.sub('\n[ ]+', '\n', text, flags=re.UNICODE)
	while True:
		newtext = text.replace('\n\n', '  ')
		if newtext == text:
			break
		else:
			text = newtext
	text = re.sub('(^\n)|(\n$)', '', text, flags=re.UNICODE)
	return text

def rand_anekdot():
	try:
		data = get('http://www.umori.li/api/get', params = {'site':'anekdot.ru', 'name':'new anekdot', 'num':50}).json()
		data = data[random.randint(0,(len(data)-1))]['elementPureHtml']
		return strip_spaces(strip_tags(data))
	except:
		return None

def rand_txt(key):
	return TEXTS[key][random.randint(1, len(TEXTS[key]))-1]

def decorator(func):
	def wrapper(bot, update):
		if not update or update.message.chat_id == CHAT:
			return func(bot, update)
	return wrapper

def prepare_update():
	global CONTEXT
	txt = CONTEXT['base_msg']
	if CONTEXT['going'] or CONTEXT['passing']:
		txt = '\n'.join([txt, u'===============\nУже высказались:', 
			'\n'.join([u'{}\t{}'.format(x, Emoji.WHITE_HEAVY_CHECK_MARK.decode('utf-8')) for x in CONTEXT['going'].values()] + [u'{}\t{}'.format(x, Emoji.CROSS_MARK.decode('utf-8')) for x in CONTEXT['passing'].values()])])
	return txt

@decorator
def mealtime_command(bot, update):
	global CONTEXT
	today = datetime.utcnow()
	base_msg = rand_txt('mealtime')
	msg = bot.sendMessage(chat_id=CHAT, text=base_msg, reply_markup=KEYBOARD)
	CONTEXT = {'time':DINNER_TIME, 'going':{}, 'passing':{}, 'message':msg.message_id, 'chat':CHAT, 'date':(today.year, today.month, today.day), 'base_msg':base_msg}

def callback_dispatcher(bot, update):
	global CONTEXT
	query = update.callback_query
	user = query.from_user
	if not CONTEXT:
		bot.answerCallbackQuery(query.id, text=rand_txt('wrong_time'))
	if query.message.message_id == CONTEXT.get('message', 0):
		if query.data == 'meal.go':
			if user.id in CONTEXT['going'].keys():
				bot.answerCallbackQuery(query.id, text=rand_txt('already_counted'))
			else:
				CONTEXT['going'][user.id] = ' '.join([user.first_name, user.last_name]).strip()
				if user.id in CONTEXT['passing'].keys():
					del CONTEXT['passing'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				else:
					bot.answerCallbackQuery(query.id, text=rand_txt('first_count'))
		elif query.data == 'meal.pass':
			if user.id in CONTEXT['passing'].keys():
				bot.answerCallbackQuery(query.id, text=rand_txt('already_counted'))
			else:
				CONTEXT['passing'][user.id] = ' '.join([user.first_name, user.last_name]).strip()
				if user.id in CONTEXT['going'].keys():
					del CONTEXT['going'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				else:
					bot.answerCallbackQuery(query.id, text=rand_txt('first_count'))
		elif query.data == 'meal.aubergine':
			bot.answerCallbackQuery(query.id, text=rand_txt('aubergine'))
		try:
			bot.editMessageText(text=prepare_update(), chat_id=CONTEXT['chat'], message_id=CONTEXT['message'], reply_markup=KEYBOARD)
		except TelegramError as e:
			if str(e) == 'Bad Request: message is not modified (400)':
				pass
			else:
				print e

dispatcher.addHandler(CommandHandler('mealtime', mealtime_command))
dispatcher.addHandler(CallbackQueryHandler(callback_dispatcher))

updater.start_polling()


while True:
	today = datetime.utcnow()
	calend = holidays()
	if today.day not in calend[today.year][today.month]:
		dinner_time = today.replace(hour=DINNER_TIME[0], minute=DINNER_TIME[1])
		if dinner_time <= today:
			CONTEXT = {}
		elif (dinner_time - today).total_seconds() <= 5*60 and not CONTEXT:
			mealtime_command(updater.bot, None)
			continue
		if today.hour > WORKING_HOURS[0] and today.hour <= WORKING_HOURS[1]:
			coin = random.random()
			print coin
			if coin <= 0.02:
				txt = rand_anekdot()
				if txt:
					txt = '\n'.join([rand_txt('anekdot'), '```', txt, '```'])
					updater.bot.sendMessage(chat_id=CHAT, text=txt, parse_mode="Markdown")
	sleep(10)


updater.idle()