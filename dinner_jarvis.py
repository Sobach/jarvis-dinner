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

from settings import TOKEN, CHAT, CALEND, WEATHER_TOKEN
TEXTS = {
	'mealtime': [u'Еда стынет. Пора собираться.', u'Ну чо сидим? Пора бежать.', u'Ай-да пожрать!', u'Шекснинска стерлядь золотая,\nКаймак и борщ уже стоят;\nВ крафинах вина, пунш, блистая\nТо льдом, то искрами, манят;\nС курильниц благовоньи льются,\nПлоды среди корзин смеются,\nНе смеют слуги и дохнуть,\nТебя стола вкруг ожидая;\nХозяйка статная, младая\nГотова руку протянуть.', u'Кушать подано, садитесь жрать, пожалуйста!'],
	'aubergine': [u'Мальчик!!!!! Ты - долбоеб!!!! Сначала идет - томат!!!', u'А я фея без хуя, пейте сок "Моя семья"!'],
	'already_counted':[u'Да я понял, понял. Уймись уже.', u'УЗБАГОЙСЯ!!!', u'Одного раза вполне достаточно.'],
	'changing_opinion':[u'Как вы, право, непостоянны...', u'Может еще передумаешь?'],
	'first_count':[u'Ok!', u'Roger that!', u'Принято!', u'Отличный выбор!'],
	'anekdot':[u'Настало время удивительных историй...', u'Что-то вы какие-то унылые.', u'Держите свежий анекдот.', u'Ребзя, приколитесь:', u'Хотите поржать? Нет? А придется.'],
	'wrong_time':[u'Не время сейчас о еде думать!', u'Займись-ка лучше делом.', u'Сколько можно жрать?', u'Ррработать!!!'],
	'weather':[u'И о погоде...', u'Гулять пойдем сегодня?', u'Утиный патруль готов к прогулке?'],
	'news':[u'ААА!!! Срочная новость!!!!', u'Мы прерываем нашу программу, чтобы передать спецрепортаж.', u'BRKNG!!!'],
}
KEYBOARD = InlineKeyboardMarkup(
	[[InlineKeyboardButton(Emoji.STEAMING_BOWL.decode('utf-8')+u' Иду', callback_data='meal.go'),
	InlineKeyboardButton(Emoji.SPEAK_NO_EVIL_MONKEY.decode('utf-8')+u' Пропускаю', callback_data='meal.pass')],
	[InlineKeyboardButton(Emoji.AUBERGINE.decode('utf-8')+u' Я баклажан', callback_data='meal.aubergine'),
	]])
FRIDAY_KEYBOARD = InlineKeyboardMarkup(
	[[InlineKeyboardButton(Emoji.STEAMING_BOWL.decode('utf-8')+u' Столовка', callback_data='meal.go'),
	InlineKeyboardButton(Emoji.HAMBURGER.decode('utf-8')+u' Вводный', callback_data='meal.junkfood')],
	[InlineKeyboardButton(Emoji.SPEAK_NO_EVIL_MONKEY.decode('utf-8')+u' Пропускаю', callback_data='meal.pass')
	]])

CONTEXT = {'dinner':{}, 'weather':{}, 'news':{}}

# MSK_TIME - 3 hrs
DINNER_TIME = (9,0)
WORKING_HOURS = (6,14)
WEATHER_TIME = (8,30)

logging.basicConfig(file="jarvis.log", level=logging.ERROR, format=u'[%(asctime)s] LINE: #%(lineno)d | %(levelname)-8s | %(message)s')

updater = Updater(token=TOKEN)
dispatcher = updater.dispatcher

def holidays():
	hd = {}
	si = StringIO(CALEND)
	cr = reader(si, delimiter = ',')
	for row in cr:
		#hd[int(row[0])] = {k:set([int(x) for x in v.split(',')]) for k, v in zip(range(1,13), row[1:13])}
		hd[int(row[0])] = {k:set([]) for k, v in zip(range(1,13), row[1:13])}
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

def breaking_news():
	global CONTEXT
	try:
		resp = get("https://twitrss.me/twitter_user_to_rss/?user=riabreakingnews")
		soup = bs4.BeautifulSoup(resp.text)
		item = soup.find("item")
		if item.guid.string != CONTEXT['news'].get('last_news', ''):
			CONTEXT['news']['last_news'] = item.guid.string
			return item.title.string
		else:
			return None
	except:
		return None

def weather():
	url = 'http://api.openweathermap.org/data/2.5/weather?lat=55.836545&lon=37.478926&lang=ru&units=metric&appid=3f391970b2a837a7c993b8d50b1ae7b9'
	icons = {
		"01d": Emoji.BLACK_SUN_WITH_RAYS.decode('utf-8'),
		"02d": Emoji.SUN_BEHIND_CLOUD.decode('utf-8'),
		"03d": Emoji.CLOUD.decode('utf-8'),
		"04d": Emoji.CLOUD.decode('utf-8'),
		"09d": Emoji.UMBRELLA_WITH_RAIN_DROPS.decode('utf-8'),
		"10d": Emoji.UMBRELLA_WITH_RAIN_DROPS.decode('utf-8'),
		"11d": Emoji.UMBRELLA_WITH_RAIN_DROPS.decode('utf-8'),
		"13d": Emoji.SNOWFLAKE.decode('utf-8'),
		"50d": Emoji.FOGGY.decode('utf-8'),
	}
	try:
		data = get(url).json()
		txt = u"{} {}. Температура воздуха: {}°C, ветер: {}, {}, влажность: {}%".format(
			icons.get(data['weather'][0]['icon'], ''),
			data['weather'][0]['description'],
			int(round(data['main']['temp'])),
			wind_speed(data['wind']['speed']),
			wind_direction(data['wind']['deg']),
			dat['main']['humidity']
		)
		return txt
	except:
		return None

def wind_direction(degrees):
	if degrees <= 22.5:
		return u"северный"
	elif degrees <=67.5:
		return u"северо-восточный"
	elif degrees <=112.5:
		return u"восточный"
	elif degrees <=157.5:
		return u"юго-восточный"
	elif degrees <=202.5:
		return u"южный"
	elif degrees <=247.5:
		return u"юго-западный"
	elif degrees <=292.5:
		return u"восточный"
	elif degrees <=337.5:
		return u"северо-восточный"
	else:
		return u"северный"

def wind_speed(speed):
	if speed <= 1.5:
		return u"тихий"
	elif speed <= 3.3:
		return u"легкий"
	elif speed <=5.4:
		return u"слабый"
	elif speed <=7.9:
		return u"умеренный"
	elif speed <=10.7:
		return u"свежий"
	elif speed <=13.8:
		return u"сильный"
	elif speed <=17.1:
		return u"крепкий"
	else:
		return u"очень крепкий"

def rand_txt(key):
	return TEXTS[key][random.randint(1, len(TEXTS[key]))-1]

def decorator(func):
	def wrapper(bot, update):
		if not update or update.message.chat_id == CHAT:
			return func(bot, update)
	return wrapper

def prepare_update():
	global CONTEXT
	txt = CONTEXT['dinner']['base_msg']
	if CONTEXT['dinner']['going'] or CONTEXT['dinner']['passing']:
		txt = '\n'.join([txt, u'===============\nУже высказались:', 
			'\n'.join([u'{}\t{}'.format(x, Emoji.HAMBURGER.decode('utf-8')) for x in CONTEXT['dinner']['junkfood'].values()] + [u'{}\t{}'.format(x, Emoji.WHITE_HEAVY_CHECK_MARK.decode('utf-8')) for x in CONTEXT['dinner']['going'].values()] + [u'{}\t{}'.format(x, Emoji.CROSS_MARK.decode('utf-8')) for x in CONTEXT['dinner']['passing'].values()])])
	return txt

@decorator
def mealtime_command(bot, update):
	global CONTEXT
	today = datetime.utcnow()
	base_msg = rand_txt('mealtime')
	if today.weekday() == 4:
		keyboard = FRIDAY_KEYBOARD
	else:
		keyboard = KEYBOARD
	msg = bot.sendMessage(chat_id=CHAT, text=base_msg, reply_markup=keyboard)
	CONTEXT['dinner'] = {'time':DINNER_TIME, 'going':{}, 'passing':{}, 'junkfood':{}, 'message':msg.message_id, 'chat':CHAT, 'date':(today.year, today.month, today.day), 'base_msg':base_msg}

def callback_dispatcher(bot, update):
	global CONTEXT
	query = update.callback_query
	user = query.from_user
	if not CONTEXT['dinner']:
		bot.answerCallbackQuery(query.id, text=rand_txt('wrong_time'))
	if query.message.message_id == CONTEXT['dinner'].get('message', 0):
		if query.data == 'meal.go':
			if user.id in CONTEXT['dinner']['going'].keys():
				bot.answerCallbackQuery(query.id, text=rand_txt('already_counted'))
			else:
				CONTEXT['dinner']['going'][user.id] = ' '.join([user.first_name, user.last_name]).strip()
				if user.id in CONTEXT['dinner']['passing'].keys():
					del CONTEXT['dinner']['passing'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				elif user.id in CONTEXT['dinner']['junkfood'].keys():
					del CONTEXT['dinner']['junkfood'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				else:
					bot.answerCallbackQuery(query.id, text=rand_txt('first_count'))
		elif query.data == 'meal.pass':
			if user.id in CONTEXT['dinner']['passing'].keys():
				bot.answerCallbackQuery(query.id, text=rand_txt('already_counted'))
			else:
				CONTEXT['dinner']['passing'][user.id] = ' '.join([user.first_name, user.last_name]).strip()
				if user.id in CONTEXT['dinner']['going'].keys():
					del CONTEXT['dinner']['going'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				elif user.id in CONTEXT['dinner']['junkfood'].keys():
					del CONTEXT['dinner']['junkfood'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				else:
					bot.answerCallbackQuery(query.id, text=rand_txt('first_count'))
		elif query.data == 'meal.junkfood':
			if user.id in CONTEXT['dinner']['junkfood'].keys():
				bot.answerCallbackQuery(query.id, text=rand_txt('already_counted'))
			else:
				CONTEXT['dinner']['junkfood'][user.id] = ' '.join([user.first_name, user.last_name]).strip()
				if user.id in CONTEXT['dinner']['going'].keys():
					del CONTEXT['dinner']['going'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				elif user.id in CONTEXT['dinner']['passing'].keys():
					del CONTEXT['dinner']['passing'][user.id]
					bot.answerCallbackQuery(query.id, text=rand_txt('changing_opinion'))
				else:
					bot.answerCallbackQuery(query.id, text=rand_txt('first_count'))
		elif query.data == 'meal.aubergine':
			bot.answerCallbackQuery(query.id, text=rand_txt('aubergine'))
		try:
			if datetime.utcnow().weekday() == 4:
				keyboard = FRIDAY_KEYBOARD
			else:
				keyboard = KEYBOARD
			bot.editMessageText(text=prepare_update(), chat_id=CONTEXT['dinner']['chat'], message_id=CONTEXT['dinner']['message'], reply_markup=keyboard)
		except TelegramError as e:
			if str(e) == 'Bad Request: message is not modified (400)':
				pass
			else:
				print e

breaking_news()
news_breaker = 6
news_iterator = 0

#dispatcher.addHandler(CommandHandler('mealtime', mealtime_command))
dispatcher.addHandler(CallbackQueryHandler(callback_dispatcher))

updater.start_polling()

while True:
	today = datetime.utcnow()
	calend = holidays()
	if today.day not in calend[today.year][today.month]:

		# SENDING DINNER MESSAGE IN TIME
		dinner_time = today.replace(hour=DINNER_TIME[0], minute=DINNER_TIME[1])
		if dinner_time <= today:
			CONTEXT['dinner'] = {}
		elif (dinner_time - today).total_seconds() <= 5*60 and not CONTEXT['dinner']:
			mealtime_command(updater.bot, None)
			continue

		# SENDING WEATHER PROGNOSIS
		weather_time = today.replace(hour=WEATHER_TIME[0], minute=WEATHER_TIME[1])
		if abs((weather_time - today).total_seconds()) < 3*60 and today.date() != CONTEXT['weather'].get('last_date', 0):
			try:
				weather_msg = weather()
			except:
				pass
			else:
				if weather_msg:
					weather_msg = '\n'.join(rand_txt('weather'), '=============', weather_msg)
					updater.bot.sendMessage(chat_id=CHAT, text=weather_msg)
					CONTEXT['weather']['last_date'] = today.date()

		# SENDING RANDOM JOKE SUDDENLY IN WORKING HOURS
		if today.hour > WORKING_HOURS[0] and today.hour <= WORKING_HOURS[1]:
			coin = random.random()
			if coin <= 0.005:
				txt = rand_anekdot()
				if txt:
					txt = '\n'.join([rand_txt('anekdot'), '```', txt, '```'])
					updater.bot.sendMessage(chat_id=CHAT, text=txt, parse_mode="Markdown")

	# LOOKING FOR BREAKING NEWS
	news_iterator+=1
	if news_iterator == news_breaker:
		news_iterator=0
		news_text = breaking_news()
		if news_text:
			news_text = '\n'.join(rand_txt('news'), '=============', news_text)
			updater.bot.sendMessage(chat_id=CHAT, text=news_text)
	sleep(10)


updater.idle()