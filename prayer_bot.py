import asyncio
import logging
import requests
import json
import datetime
import re
import pytz
from datetime import timezone
import aioschedule
import os
import random
import sys
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

# Import our custom modules
from quron_data import QURAN_SURAHS, QURAN_SURAH_LINKS
from language_manager import LanguageManager, LANG_UZ_LATIN, LANG_UZ_CYRILLIC, LANG_RU, LANG_KZ, LANG_KG, \
	DEFAULT_LANGUAGE
from ui_buttons import create_language_keyboard, create_main_keyboard, create_location_keyboard, create_admin_keyboard, \
	create_cancel_keyboard, create_help_keyboard, create_quran_keyboard, create_organ_keyboard

# Set up logging to console with more detailed information
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	handlers=[
		logging.StreamHandler(sys.stdout)
	]
)

# Configuration
TOKEN = "7282036850:AAFerP8w9Vbt9Jiv_m7ulL0vY6z5c8LHdKk"  # Replace with your actual bot token
ADMIN_ID = 7000454062  # Replace with your actual admin ID
API_BASE = "http://api.aladhan.com/v1/calendar?method=14&school=1&"
NAMOZ_API = "https://namozvaqti.uz/api/present/day?region="
USER_DATA_FILE = "users.txt"
QURAN_CHANNEL_ID = "kanalquron"
REQUIRED_CHANNEL_FILE = "required_channel.txt"

# Set Uzbekistan time zone (UTC+5)
UZBEKISTAN_TZ = pytz.timezone('Asia/Tashkent')

# Bot version and information
BOT_VERSION = "1.5.0"
BOT_CREATED_DATE = "2023-05-15"
BOT_LAST_UPDATED = "2023-08-25"

# Qibla finder URL
QIBLA_FINDER_URL = "https://www.qiblafinder.org/qibla-direction?lat={lat}&long={lon}"

# Check if token is valid
if TOKEN == "YOUR_BOT_TOKEN":
	logging.error("Please set your bot token in the TOKEN variable")
	print("ERROR: Bot token not set! Please replace 'YOUR_BOT_TOKEN' with your actual bot token.")
	sys.exit(1)

try:
	# Initialize bot and dispatcher with memory storage for states
	storage = MemoryStorage()
	bot = Bot(token=TOKEN)
	dp = Dispatcher(storage=storage)
	logging.info("Bot and dispatcher initialized successfully")
except Exception as e:
	logging.error(f"Failed to initialize bot: {e}")
	print(f"ERROR: Failed to initialize bot: {e}")
	sys.exit(1)

# Initialize language manager
lang_manager = LanguageManager()

# Define states for admin broadcast, quran navigation, and channel setting
class BroadcastStates(StatesGroup):
	waiting_for_message = State()

class QuranStates(StatesGroup):
	selecting_surah = State()

class ChannelStates(StatesGroup):
	waiting_for_channel = State()

# Define a state for language selection
class LanguageStates(StatesGroup):
	selecting_language = State()

# Define states for admin operations
class AdminStates(StatesGroup):
	waiting_for_broadcast = State()
	waiting_for_channel = State()

# Helper Functions
def get_current_time_uz():
	"""Get current time in Uzbekistan"""
	return datetime.datetime.now(UZBEKISTAN_TZ)

def get_hijri_date(gregorian_date):
	"""Get approximate Hijri date from Gregorian date"""
	# This is a very simple approximation
	# For a real implementation, use a proper Hijri calendar library
	year = gregorian_date.year
	month = gregorian_date.month
	day = gregorian_date.day
	
	# Approximate conversion (not accurate)
	hijri_year = int(year - 622 + (year - 622) / 32)
	
	# Approximate Ramadan month names
	hijri_months = [
		"Муҳаррам", "Сафар", "Рабиул-аввал", "Рабиул-охир",
		"Жумодул-аввал", "Жумодул-охир", "Ражаб", "Шаъбон",
		"Рамазон", "Шаввол", "Зулқаъда", "Зулҳижжа"
	]
	
	# Approximate current Hijri month
	hijri_month_idx = (month + 1) % 12  # Simple offset
	hijri_month = hijri_months[hijri_month_idx]
	
	return f"{day} {hijri_month}, {hijri_year} ҳ.й."

async def check_membership(user_id):
	"""Check if user is a member of the required channel"""
	try:
		required_channel = get_required_channel()
		if not required_channel:
			return True  # No required channel, so user is considered a member
		
		channel_id = required_channel["channel_id"]
		
		# Try to get chat member info
		chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
		
		# Check if user is a member
		return chat_member.status in ['member', 'administrator', 'creator']
	except Exception as e:
		logging.error(f"Error checking membership: {e}")
		return False  # Assume not a member on error

def get_required_channel():
	"""Get required channel info"""
	try:
		with open(REQUIRED_CHANNEL_FILE, "r", encoding="utf-8") as file:
			data = file.read().strip().split(",")
			if len(data) >= 3:
				return {
					"channel_id": data[0],
					"channel_name": data[1],
					"channel_link": data[2]
				}
	except FileNotFoundError:
		return None
	except Exception as e:
		logging.error(f"Error getting required channel: {e}")
		return None

def save_required_channel(channel_id, channel_name, channel_link):
	"""Save required channel info"""
	try:
		with open(REQUIRED_CHANNEL_FILE, "w", encoding="utf-8") as file:
			file.write(f"{channel_id},{channel_name},{channel_link}")
		return True
	except Exception as e:
		logging.error(f"Error saving required channel: {e}")
		return False

def delete_required_channel():
	"""Delete required channel"""
	try:
		if os.path.exists(REQUIRED_CHANNEL_FILE):
			os.remove(REQUIRED_CHANNEL_FILE)
			return True
		return False
	except Exception as e:
		logging.error(f"Error deleting required channel: {e}")
		return False

async def broadcast_message_to_all(message_text, parse_mode=None):
	"""Broadcast message to all users"""
	users = get_all_users()
	sent_count = 0
	failed_count = 0
	
	for user in users:
		try:
			await bot.send_message(
				chat_id=user["user_id"],
				text=message_text,
				parse_mode=parse_mode
			)
			sent_count += 1
			# Add a small delay to avoid hitting rate limits
			await asyncio.sleep(0.1)
		except Exception as e:
			logging.error(f"Failed to send broadcast to user {user['user_id']}: {e}")
			failed_count += 1
	
	return sent_count, failed_count

async def get_prayer_times_namozvaqti(city):
	"""Get prayer times from namozvaqti.uz"""
	try:
		# Convert city name to lowercase and replace spaces with underscores
		city_formatted = city.lower().replace(" ", "_")
		
		url = f"{NAMOZ_API}{city_formatted}"
		response = requests.get(url)
		
		if response.status_code == 200:
			data = response.json()
			
			# Extract prayer times
			times = data.get("times", {})
			
			return {
				"fajr": times.get("tong_saharlik"),
				"sunrise": times.get("quyosh"),
				"dhuhr": times.get("peshin"),
				"asr": times.get("asr"),
				"maghrib": times.get("shom_iftor"),
				"isha": times.get("hufton")
			}
		return None
	except Exception as e:
		logging.error(f"Error getting prayer times from namozvaqti.uz: {e}")
		return None

async def get_prayer_times_aladhan(lat, lon):
	"""Get prayer times from aladhan.com"""
	try:
		# Get current date
		now = get_current_time_uz()
		month = now.month
		year = now.year
		
		url = f"{API_BASE}latitude={lat}&longitude={lon}&month={month}&year={year}"
		response = requests.get(url)
		
		if response.status_code == 200:
			data = response.json()
			
			# Get today's date
			today = now.day
			
			# Find today's prayer times
			for day_data in data.get("data", []):
				if day_data.get("date", {}).get("gregorian", {}).get("day") == str(today):
					times = day_data.get("timings", {})
					
					# Extract and format prayer times (remove timezone info)
					return {
						"fajr": times.get("Fajr", "").split(" ")[0],
						"sunrise": times.get("Sunrise", "").split(" ")[0],
						"dhuhr": times.get("Dhuhr", "").split(" ")[0],
						"asr": times.get("Asr", "").split(" ")[0],
						"maghrib": times.get("Maghrib", "").split(" ")[0],
						"isha": times.get("Isha", "").split(" ")[0]
					}
		return None
	except Exception as e:
		logging.error(f"Error getting prayer times from aladhan.com: {e}")
		return None

def save_user_data(user_id, username, full_name, city, lat, lon, lang=LANG_UZ_LATIN):
	"""Save user data to file"""
	try:
		with open(USER_DATA_FILE, "a+", encoding="utf-8") as file:
			file.seek(0)
			users = file.readlines()
			
			# Check if user already exists
			for i, user in enumerate(users):
				user_info = user.strip().split(",")
				if user_info[0] == str(user_id):
					# Update existing user
					# If there's already a language field, use it; otherwise, add the default
					if len(user_info) >= 7:
						lang = user_info[6] if lang is None else lang
					
					users[i] = f"{user_id},{username},{full_name},{city},{lat},{lon},{lang}\n"
					
					# Rewrite the file
					file.seek(0)
					file.truncate()
					file.writelines(users)
					return
			
			# Add new user
			file.write(f"{user_id},{username},{full_name},{city},{lat},{lon},{lang}\n")
	except Exception as e:
		logging.error(f"Error saving user data: {e}")

def get_user_data(user_id):
	"""Get user data from file"""
	try:
		with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
			users = file.readlines()
			
			for user in users:
				user_info = user.strip().split(",")
				if len(user_info) >= 6 and user_info[0] == str(user_id):
					# Default language to Uzbek Latin if not specified
					lang = user_info[6] if len(user_info) >= 7 else LANG_UZ_LATIN
					
					return {
						"user_id": user_info[0],
						"username": user_info[1],
						"full_name": user_info[2],
						"city": user_info[3],
						"lat": user_info[4],
						"lon": user_info[5],
						"lang": lang
					}
	except FileNotFoundError:
		return None
	except Exception as e:
		logging.error(f"Error getting user data: {e}")
		return None

def get_all_users():
	"""Get all users from file"""
	try:
		with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
			users = file.readlines()
			
			user_list = []
			for user in users:
				user_info = user.strip().split(",")
				if len(user_info) >= 6:
					# Default language to Uzbek Latin if not specified
					lang = user_info[6] if len(user_info) >= 7 else LANG_UZ_LATIN
					
					user_list.append({
						"user_id": user_info[0],
						"username": user_info[1],
						"full_name": user_info[2],
						"city": user_info[3],
						"lat": user_info[4],
						"lon": user_info[5],
						"lang": lang
					})
			return user_list
	except FileNotFoundError:
		return []
	except Exception as e:
		logging.error(f"Error getting all users: {e}")
		return []

def update_user_language(user_id, lang):
	"""Update user language"""
	try:
		user_data = get_user_data(user_id)
		if user_data:
			save_user_data(
				user_id=user_id,
				username=user_data["username"],
				full_name=user_data["full_name"],
				city=user_data["city"],
				lat=user_data["lat"],
				lon=user_data["lon"],
				lang=lang
			)
			return True
		return False
	except Exception as e:
		logging.error(f"Error updating user language: {e}")
		return False

def get_text(user_id, key, **kwargs):
	"""Get text in the user's language"""
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN  # Default language
	
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Use the language manager to get the text
	return lang_manager.get_text(lang, key, **kwargs)

def get_prayer_period_text(user_id, period):
	"""Get prayer period in the user's language"""
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN  # Default language
	
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Use the language manager to get the nested text
	return lang_manager.get_nested_text(lang, "prayer_periods", period, period)

def get_current_prayer_period(prayer_times):
	"""Get current prayer period"""
	if not prayer_times:
		return None
	
	# Get current time in Uzbekistan
	now = get_current_time_uz().strftime("%H:%M")
	
	if now >= prayer_times["fajr"] and now < prayer_times["sunrise"]:
		return "fajr"
	if now >= prayer_times["sunrise"] and now < prayer_times["dhuhr"]:
		return "sunrise"
	if now >= prayer_times["dhuhr"] and now < prayer_times["asr"]:
		return "dhuhr"
	if now >= prayer_times["asr"] and now < prayer_times["maghrib"]:
		return "asr"
	if now >= prayer_times["maghrib"] and now < prayer_times["isha"]:
		return "maghrib"
	return "isha"

async def format_prayer_times_message(prayer_times, city, user_id, api_source=""):
	"""Format prayer times message"""
	# Get current time in Uzbekistan
	current_time = get_current_time_uz().strftime("%H:%M")
	current_prayer_period = get_current_prayer_period(prayer_times)
	current_prayer_text = get_prayer_period_text(user_id, current_prayer_period)
	
	text = get_text(user_id, "prayer_times_title", city=city) + "\n\n"
	
	if current_prayer_period:
		text += get_text(user_id, "current_time", time=current_time, prayer=current_prayer_text) + "\n\n"
	
	text += (
		f"{get_text(user_id, 'sunrise')} {prayer_times['sunrise']}\n\n"
		f"{get_text(user_id, 'fajr')} {prayer_times['fajr']}\n"
		f"{get_text(user_id, 'dhuhr')} {prayer_times['dhuhr']}\n"
		f"{get_text(user_id, 'asr')} {prayer_times['asr']}\n"
		f"{get_text(user_id, 'maghrib')} {prayer_times['maghrib']}\n"
		f"{get_text(user_id, 'isha')} {prayer_times['isha']}\n\n"
	)
	
	text += get_text(user_id, "calculation_method") + "\n"
	
	return text

async def send_daily_prayer_times():
	"""Send daily prayer times to all users"""
	try:
		logging.info("Starting daily prayer times notification at 03:30")
		users = get_all_users()
		sent_count = 0
		failed_count = 0
		
		# Get current date in Uzbekistan time zone
		now = get_current_time_uz()
		today_date = now.strftime("%d.%m.%Y")
		
		for user in users:
			try:
				user_id = user["user_id"]
				city = user["city"]
				lat = user["lat"]
				lon = user["lon"]
				
				# Try to get prayer times from namozvaqti.uz first
				prayer_times = await get_prayer_times_namozvaqti(city)
				api_source = "namozvaqti.uz"
				
				# If that fails, use aladhan.com as backup
				if not prayer_times:
					prayer_times = await get_prayer_times_aladhan(lat, lon)
					api_source = "aladhan.com"
				
				if prayer_times:
					# Create a special daily notification message
					text = (
						f"{get_text(user_id, 'daily_prayer_times', date=today_date)}\n\n"
						f"{get_text(user_id, 'prayer_times_title', city=city)}\n\n"
						f"{get_text(user_id, 'fajr')} {prayer_times['fajr']}\n"
						f"{get_text(user_id, 'sunrise')} {prayer_times['sunrise']}\n"
						f"{get_text(user_id, 'dhuhr')} {prayer_times['dhuhr']}\n"
						f"{get_text(user_id, 'asr')} {prayer_times['asr']}\n"
						f"{get_text(user_id, 'maghrib')} {prayer_times['maghrib']}\n"
						f"{get_text(user_id, 'isha')} {prayer_times['isha']}\n\n"
						f"{get_text(user_id, 'calculation_method')}\n\n"
						f"<i>{get_text(user_id, 'daily_notification_note')}</i>"
					)
					
					# Create inline keyboard
					mosque_button = InlineKeyboardButton(
						text=get_text(user_id, "nearby_mosques"),
						web_app=WebAppInfo(url=f"https://www.google.com/maps/search/Mosques/@{lat},{lon},16z")
					)
					
					coder_btn = InlineKeyboardButton(
						text=get_text(user_id, "developer"),
						web_app=WebAppInfo(url=f"https://roobotmee.uz")
					)
					
					taklif = InlineKeyboardButton(
						text=get_text(user_id, "taklif"),
						url="https://t.me/roobotmee"
					)
					quran_button = InlineKeyboardButton(text=get_text(user_id, "quran"), callback_data="quran")
					help_button = InlineKeyboardButton(text=get_text(user_id, "help"), callback_data="help")
					
					# Create the keyboard with inline_keyboard parameter
					keyboard = InlineKeyboardMarkup(inline_keyboard=[
						[mosque_button],
						[quran_button],
						[coder_btn],
						[taklif]
					])
					
					await bot.send_message(
						chat_id=user_id,
						text=text,
						parse_mode="HTML",
						reply_markup=keyboard
					)
					sent_count += 1
				else:
					await bot.send_message(
						chat_id=user_id,
						text=get_text(user_id, "error_prayer_times")
					)
					failed_count += 1
				
				# Add a small delay to avoid hitting rate limits
				await asyncio.sleep(0.1)
			except Exception as e:
				logging.error(f"Failed to send daily prayer times to user {user['user_id']}: {e}")
				failed_count += 1
		
		logging.info(f"Daily prayer times sent to {sent_count} users, failed for {failed_count} users")
	except Exception as e:
		logging.error(f"Error in daily prayer times notification task: {e}")

async def scheduler():
	"""Scheduler for periodic tasks"""
	# Schedule daily prayer time updates at 15:22 (Uzbekistan time)
	aioschedule.every().day.at("15:22").do(lambda: asyncio.create_task(send_prayer_times_to_all()))
	
	# Schedule daily prayer time notifications at 03:30 (Uzbekistan time)
	aioschedule.every().day.at("03:30").do(lambda: asyncio.create_task(send_daily_prayer_times()))
	
	while True:
		await aioschedule.run_pending()
		await asyncio.sleep(60)

async def send_prayer_times_to_all():
	"""Send prayer times to all users"""
	try:
		users = get_all_users()
		sent_count = 0
		failed_count = 0
		
		for user in users:
			try:
				user_id = user["user_id"]
				city = user["city"]
				lat = user["lat"]
				lon = user["lon"]
				
				# Try to get prayer times from namozvaqti.uz first
				prayer_times = await get_prayer_times_namozvaqti(city)
				api_source = "namozvaqti.uz"
				
				# If that fails, use aladhan.com as backup
				if not prayer_times:
					prayer_times = await get_prayer_times_aladhan(lat, lon)
					api_source = "aladhan.com"
				
				if prayer_times:
					text = await format_prayer_times_message(prayer_times, city, user_id, api_source)
					
					# Create inline keyboard
					mosque_button = InlineKeyboardButton(
						text=get_text(user_id, "nearby_mosques"),
						web_app=WebAppInfo(url=f"https://www.google.com/maps/search/Mosques/@{lat},{lon},16z")
					)
					coder_btn = InlineKeyboardButton(
						text=get_text(user_id, "developer"),
						web_app=WebAppInfo(url=f"https://roobotmee.uz")
					)
					taklif = InlineKeyboardButton(
						text=get_text(user_id, "taklif"),
						url="https://t.me/roobotmee"
					)
					quran_button = InlineKeyboardButton(text=get_text(user_id, "quran"), callback_data="quran")
					help_button = InlineKeyboardButton(text=get_text(user_id, "help"), callback_data="help")
					
					# Create the keyboard with inline_keyboard parameter
					keyboard = InlineKeyboardMarkup(inline_keyboard=[
						[mosque_button],
						[quran_button],
						[coder_btn],
						[taklif]
					])
					
					await bot.send_message(
						chat_id=user_id,
						text=text,
						parse_mode="HTML",
						reply_markup=keyboard
					)
					sent_count += 1
				else:
					await bot.send_message(
						chat_id=user_id,
						text=get_text(user_id, "error_prayer_times")
					)
					failed_count += 1
				
				# Add a small delay to avoid hitting rate limits
				await asyncio.sleep(0.1)
			except Exception as e:
				logging.error(f"Failed to send prayer times to user {user['user_id']}: {e}")
				failed_count += 1
		
		logging.info(f"Prayer times sent to {sent_count} users, failed for {failed_count} users")
	except Exception as e:
		logging.error(f"Error in scheduled task: {e}")

async def send_join_channel_message(user_id):
	"""Send channel join message"""
	required_channel = get_required_channel()
	if not required_channel:
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Create join button
	join_button = InlineKeyboardButton(
		text=get_text(user_id, "join_button"),
		url=required_channel["channel_link"]
	)
	check_button = InlineKeyboardButton(
		text=get_text(user_id, "check_button"),
		callback_data="check_membership"
	)
	
	keyboard = InlineKeyboardMarkup(inline_keyboard=[
		[join_button],
		[check_button]
	])
	
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "join_channel", channel=required_channel["channel_name"]),
		parse_mode="HTML",
		reply_markup=keyboard
	)

def get_random_hadith():
	"""Tasodifiy hadis olish"""
	hadiths = [
		{
			"text": "Eng yaxshilaringiz oilasiga eng yaxshi muomala qiladiganlaringizdir.",
			"source": "Tirmiziy"
		},
		{
			"text": "Hech kimingiz chinakam iymonli emas, toki ukasi uchun o'zi istagan narsani istaguncha.",
			"source": "Buxoriy va Muslim"
		},
		{
			"text": "Allohga eng yoqadigan amallar - doimiy bajarilydigan amallardir, hatto ular oz bo'lsa ham.",
			"source": "Buxoriy va Muslim"
		},
		{
			"text": "Kim Allohga va Oxirat kuniga ishonadigan bo'lsa, u yaxshi gapirsin yoki sukut saqlasin.",
			"source": "Buxoriy va Muslim"
		},
		{
			"text": "Birodaringiz oldida tabassum qilish - sadaqadir.",
			"source": "Tirmiziy"
		},
		{
			"text": "Kuchli odam - boshqasini yengadigan kishi emas. Kuchli odam - g'azablanganda o'zini tuta oladigan kishidir.",
			"source": "Buxoriy"
		},
		{
			"text": "Ishlarni osonlashtiring, qiyinlashtirmang, odamlarni xursand qiling, ularni haydab yubormang.",
			"source": "Buxoriy"
		},
		{
			"text": "Boshqalarga rahm qilmaydigan kishiga rahm qilinmaydi.",
			"source": "Buxoriy va Muslim"
		},
		{
			"text": "Iymoni eng mukammal bo'lgan mo'minlar - xulqi eng yaxshi bo'lganlardir. Sizlarning eng yaxshilaringiz - xotinlariga eng yaxshi muomala qiladiganlaringizdir.",
			"source": "Tirmiziy"
		},
		{
			"text": "Kim bir mo'minning bu dunyodagi qiyinchiligini yengillashtirsa, Alloh uni Oxiratdagi qiyinchiliklardan qutqaradi.",
			"source": "Muslim"
		}
	]
	return random.choice(hadiths)

def get_random_dhikr():
	"""Tasodifiy zikr olish"""
	dhikrs = [
		{
			"arabic": "سُبْحَانَ اللهِ وَبِحَمْدِهِ",
			"transliteration": "Subhanallahi wa bihamdihi",
			"translation": "Alloh pokdir va hamd Unga tegishli",
			"virtue": "Kim kuniga yuz marta 'Subhanallahi wa bihamdihi' desa, dengiz ko'piklaricha gunohlari bo'lsa ham, ularning barchasi kechiriladi."
		},
		{
			"arabic": "لا إله إلا الله وحده لا شريك له، له الملك وله الحمد وهو على كل شيء قدير",
			"transliteration": "La ilaha illallah wahdahu la sharika lah, lahul mulku wa lahul hamdu wa huwa 'ala kulli shay'in qadir",
			"translation": "Allohdan boshqa iloh yo'q, U yolg'izdir, sherigi yo'q. Podshohlik va hamd Unga tegishli va U har narsaga qodirdir.",
			"virtue": "Kim ertalab bu zikrni 10 marta aytgan bo'lsa, unga 100 yaxshi amal yoziladi, 100 yomon amali o'chiriladi, 10 qul ozod qilgan savobi beriladi va shaytondan kechgacha himoyalanadi."
		},
		{
			"arabic": "أَسْتَغْفِرُ اللهَ وَأَتُوبُ إِلَيْهِ",
			"transliteration": "Astaghfirullah wa atubu ilayh",
			"translation": "Allohdan mag'firat so'rayman va Unga tavba qilaman",
			"virtue": "Payg'ambarimiz (s.a.v.): 'Allohga qasamki, men kuniga 70 martadan ko'proq Allohdan mag'firat so'rab, Unga tavba qilaman' dedilar."
		},
		{
			"arabic": "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ",
			"transliteration": "Allahumma salli 'ala Muhammad wa 'ala aali Muhammad",
			"translation": "Ey Allohim, Muhammadga va Muhammad oilasiga salovat yubor",
			"virtue": "Kim bir marta menga salovat aytgan bo'lsa, Alloh unga o'n marta rahmat aytadi."
		},
		{
			"arabic": "لا حَوْلَ وَلا قُوَّةَ إِلا بِاللهِ",
			"transliteration": "La hawla wa la quwwata illa billah",
			"translation": "Kuch-quvvat faqat Alloh bilan",
			"virtue": "Bu ibora Jannat xazinalaridan bir xazinadir."
		}
	]
	return random.choice(dhikrs)

def get_dhikr_by_category(category):
	"""Turkum bo'yicha zikr olish"""
	# Har bir turkum uchun namuna zikrlar
	morning_dhikrs = [
		{
			"arabic": "أَصْبَحْنَا وَأَصْبَحَ الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لاَ إِلَهَ إِلاَّ اللهُ وَحْدَهُ لاَ شَرِيكَ لَهُ",
			"transliteration": "Asbahna wa asbahal mulku lillah, walhamdu lillah, la ilaha illallah wahdahu la sharika lah",
			"translation": "Biz tongga yetdik va hozir podshohlik Allohga tegishli. Hamd Allohga. Allohdan boshqa iloh yo'q, U yolg'izdir, sherigi yo'q.",
			"virtue": "Kim ertalab bu zikrni aytgan bo'lsa, Allohga shu kun uchun shukr aytgan bo'ladi."
		}
	]
	
	evening_dhikrs = [
		{
			"arabic": "أَمْسَيْنَا وَأَمْسَى الْمُلْكُ لِلَّهِ، وَالْحَمْدُ لِلَّهِ، لاَ إِلَهَ إِلاَّ اللهُ وَحْدَهُ لاَ شَرِيكَ لَهُ",
			"transliteration": "Amsayna wa amsal mulku lillah, walhamdu lillah, la ilaha illallah wahdahu la sharika lah",
			"translation": "Biz kechga yetdik va hozir podshohlik Allohga tegishli. Hamd Allohga. Allohdan boshqa iloh yo'q, U yolg'izdir, sherigi yo'q.",
			"virtue": "Kim kechqurun bu zikrni aytgan bo'lsa, Allohga shu tun uchun shukr aytgan bo'ladi."
		}
	]
	
	salawat_dhikrs = [
		{
			"arabic": "اللَّهُمَّ صَلِّ عَلَى مُحَمَّدٍ وَعَلَى آلِ مُحَمَّدٍ كَمَا صَلَّيْتَ عَلَى إِبْرَاهِيمَ وَعَلَى آلِ إِبْرَاهِيمَ إِنَّكَ حَمِيدٌ مَجِيدٌ",
			"transliteration": "Allahumma salli 'ala Muhammad wa 'ala aali Muhammad kama sallayta 'ala Ibrahima wa 'ala aali Ibrahim, innaka Hamidun Majid",
			"translation": "Ey Allohim, Muhammadga va Muhammad oilasiga salovat yubor, Ibrohimga va Ibrohim oilasiga salovat yuborganing kabi. Albatta, Sen hamdu maqtuqsan, ulug'san.",
			"virtue": "Payg'ambarimiz (s.a.v.): 'Kim bir marta menga salovat aytgan bo'lsa, Alloh unga o'n marta rahmat aytadi' dedilar."
		}
	]
	
	tasbih_dhikrs = [
		{
			"arabic": "سُبْحَانَ اللهِ، وَالْحَمْدُ لِلَّهِ، وَلاَ إِلَهَ إِلاَّ اللهُ، وَاللهُ أَكْبَرُ",
			"transliteration": "Subhanallah, walhamdu lillah, wa la ilaha illallah, wallahu akbar",
			"translation": "Alloh pokdir, hamd Allohga tegishli, Allohdan boshqa iloh yo'q va Alloh ulug'dir.",
			"virtue": "Bu so'zlar Allohga eng yoqadigan so'zlardir va yaxshi amallar tarozi og'irligida og'irdir."
		}
	]
	
	# Turkumga qarab zikr qaytarish
	if category == "morning":
		return random.choice(morning_dhikrs)
	elif category == "evening":
		return random.choice(evening_dhikrs)
	elif category == "salawat":
		return random.choice(salawat_dhikrs)
	elif category == "tasbih":
		return random.choice(tasbih_dhikrs)
	else:
		return get_random_dhikr()

def get_audio_quran_link(reciter, surah_number):
	"""Qori va sura raqami bo'yicha Qur'on audio havolasini olish"""
	# Turli qorilar uchun asosiy URL manzillar
	base_urls = {
		"mishary": "https://server8.mp3quran.net/afs/",
		"sudais": "https://server11.mp3quran.net/sds/"
	}
	
	# Sura raqamini oldida nollar bilan formatlash
	formatted_surah = f"{surah_number:03d}"
	
	# To'liq URL manzilni qaytarish
	return f"{base_urls.get(reciter, base_urls['mishary'])}{formatted_surah}.mp3"


def get_islamic_holidays(year):
    """Berilgan yil uchun islomiy bayramlar ro‘yxati"""
    # Bu soddalashtirilgan versiya, aniq hijriy sanalar uchun maxsus taqvim kutubxonasidan foydalanish lozim.

    holidays_text = f"🌙 {year}-yilning islomiy bayramlari:\n\n"

    # Bayramlar va ularning taxminiy sanalari
    holidays = [
        {"name": "Ramazon", "date": f"Mart - Aprel {year}"},
        {"name": "Ramazon hayiti (Eid al-Fitr)", "date": f"Aprel - May {year}"},
        {"name": "Haj", "date": f"Iyun - Iyul {year}"},
        {"name": "Qurbon hayiti (Eid al-Adha)", "date": f"Iyun - Iyul {year}"},
        {"name": "Hijriy yangi yil", "date": f"Iyul - Avgust {year}"},
        {"name": "Ashuro kuni", "date": f"Iyul - Avgust {year}"},
        {"name": "Mavlud an-Nabi (Payg‘ambarimizning tug‘ilgan kuni)", "date": f"Sentabr - Oktabr {year}"}
    ]

    for holiday in holidays:
        holidays_text += f"• {holiday['name']}: {holiday['date']}\n"

    holidays_text += "\n📌 Eslatma: Aniq sanalar oy ko‘rinishiga bog‘liq bo‘lib, hududingizga qarab farq qilishi mumkin."

    return holidays_text


def get_islamic_holidays_calendar(current_year, next_year):
	"""Get Islamic holidays calendar for current and next year"""
	# This would normally use a proper Hijri calendar library
	
	calendar_text = f"<b>🗓 Islamic Calendar {current_year}-{next_year}</b>\n\n"
	calendar_text += f"<b>{current_year}</b>\n"
	calendar_text += "• Ramadan: March 23 - April 21\n"
	calendar_text += "• Eid al-Fitr: April 22\n"
	calendar_text += "• Hajj: June 26 - July 1\n"
	calendar_text += "• Eid al-Adha: June 29\n"
	calendar_text += "• Islamic New Year: July 19\n"
	calendar_text += "• Ashura: July 28\n"
	calendar_text += "• Mawlid al-Nabi: September 27\n\n"
	
	calendar_text += f"<b>{next_year}</b>\n"
	calendar_text += "• Ramadan: March 12 - April 10\n"
	calendar_text += "• Eid al-Fitr: April 11\n"
	calendar_text += "• Hajj: June 15 - June 20\n"
	calendar_text += "• Eid al-Adha: June 18\n"
	calendar_text += "• Islamic New Year: July 8\n"
	calendar_text += "• Ashura: July 17\n"
	calendar_text += "• Mawlid al-Nabi: September 16\n\n"
	
	calendar_text += "<i>Note: Dates are approximate and may vary based on moon sighting.</i>"
	
	return calendar_text

# Get all cancel command variants in different languages
def get_cancel_commands():
	"""Get all cancel command variants in different languages"""
	return [
		"❌ Bekor qilish",  # Uzbek Latin
		"❌ Бекор қилиш",  # Uzbek Cyrillic
		"❌ Отмена",  # Russian
		"❌ Болдырмау",  # Kazakh
		"❌ Жокко чыгаруу"  # Kyrgyz
	]

# Create a function to get all possible command variants in all languages
def get_command_variants(command_key):
	"""Get all language variants of a specific command"""
	variants = []
	for lang_code in [LANG_UZ_LATIN, LANG_UZ_CYRILLIC, LANG_RU, LANG_KZ, LANG_KG]:
		command = lang_manager.get_text(lang_code, command_key)
		if command and command not in variants:
			variants.append(command)
	return variants

# Bot Handlers
@dp.message(Command("start"))
async def start_command(message: types.Message):
	"""Handle start command"""
	try:
		user_id = message.from_user.id
		logging.info(f"Received /start command from user {user_id}")
		
		# Check if user is a member of the required channel
		membership_result = await check_membership(user_id)
		logging.info(f"Membership check for user {user_id}: {membership_result}")
		
		if not membership_result:
			logging.info(f"Sending join channel message to user {user_id}")
			await send_join_channel_message(user_id)
			return
		
		user_data = get_user_data(user_id)
		logging.info(f"User data for {user_id}: {user_data is not None}")
		
		if user_data:
			# Always use Uzbek Latin as default language
			lang = user_data.get("lang", LANG_UZ_LATIN)
			await message.answer(
				f"{get_text(user_id, 'welcome')}\n\n"
				f"{get_text(user_id, 'welcome_message')}",
				reply_markup=create_main_keyboard(lang, lang_manager)
			)
		else:
			# For new users, show welcome message and request location
			await message.answer(
				f"{get_text(user_id, 'welcome')} {message.from_user.full_name}!\n\n"
				f"{get_text(user_id, 'location_request')}",
				reply_markup=create_location_keyboard(LANG_UZ_LATIN, lang_manager)
			)
	except Exception as e:
		logging.error(f"Error handling /start command from user {message.from_user.id}: {e}")
		# Send a fallback message
		await message.answer(
			"Botda texnik nosozlik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring yoki /start buyrug'ini qayta yuboring.",
			reply_markup=create_location_keyboard(LANG_UZ_LATIN, lang_manager)
		)

@dp.message(lambda message: message.text in ["🌐 Til / Язык", "🌐 Тил / Язык", "🌐 Тіл / Язык"])
async def language_command(message: types.Message):
	"""Handle language command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	await message.answer(
		"🌐 Tilni tanlang / Выберите язык / Тілді таңдаңыз / Тилди тандаңыз",
		reply_markup=create_language_keyboard()
	)

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def language_callback(callback_query: types.CallbackQuery):
	"""Handle language selection callback"""
	user_id = callback_query.from_user.id
	lang_code = callback_query.data.split("_")[1]
	
	# Update user language
	update_user_language(user_id, lang_code)
	
	# Send confirmation message
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "language_updated"),
		reply_markup=create_main_keyboard(lang_code, lang_manager)
	)
	
	# Answer callback query
	await callback_query.answer()

# Add a handler for cancel commands in all languages
@dp.message(lambda message: message.text in get_cancel_commands())
async def cancel_command(message: types.Message):
	"""Handle cancel command in all languages"""
	user_id = message.from_user.id
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Send main menu
	await message.answer(
		get_text(user_id, "main_menu"),
		reply_markup=create_main_keyboard(lang, lang_manager)
	)

# Prayer times command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("prayer_times"))
async def prayer_times_command(message: types.Message):
	"""Handle prayer times command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	if not user_data:
		await message.answer(
			get_text(user_id, "location_request"),
			reply_markup=create_location_keyboard(lang, lang_manager)
		)
		return
	
	city = user_data["city"]
	lat = user_data["lat"]
	lon = user_data["lon"]
	
	# Try to get prayer times from namozvaqti.uz first
	prayer_times = await get_prayer_times_namozvaqti(city)
	api_source = "namozvaqti.uz"
	
	# If that fails, use aladhan.com as backup
	if not prayer_times:
		prayer_times = await get_prayer_times_aladhan(lat, lon)
		api_source = "aladhan.com"
	
	if prayer_times:
		text = await format_prayer_times_message(prayer_times, city, user_id, api_source)
		
		# Create inline keyboard
		mosque_button = InlineKeyboardButton(
			text=get_text(user_id, "nearby_mosques"),
			web_app=WebAppInfo(url=f"https://www.google.com/maps/search/Mosques/@{lat},{lon},16z")
		)
		coder_btn = InlineKeyboardButton(
			text=get_text(user_id, "developer"),
			web_app=WebAppInfo(url=f"https://roobotmee.uz")
		)
		
		taklif = InlineKeyboardButton(
			text=get_text(user_id, "taklif"),
			url="https://t.me/roobotmee"
		)
		
		quran_button = InlineKeyboardButton(text=get_text(user_id, "quran"), callback_data="quran")
		help_button = InlineKeyboardButton(text=get_text(user_id, "help"), callback_data="help")
		
		# Create the keyboard with inline_keyboard parameter
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[mosque_button],
			[quran_button],
			[coder_btn],
			[taklif]
		])
		
		await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
	else:
		await message.answer(get_text(user_id, "error_prayer_times"))

# Quran command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("quran"))
async def quran_command(message: types.Message):
	"""Handle Quran command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await message.answer(
		get_text(user_id, "quran_title"),
		parse_mode="HTML",
		reply_markup=create_quran_keyboard(page=1, lang_code=lang, lang_manager=lang_manager)
	)

# Qibla command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("qibla"))
async def qibla_command(message: types.Message):
	"""Handle Qibla command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	if not user_data:
		await message.answer(
			get_text(user_id, "location_request"),
			reply_markup=create_location_keyboard(lang, lang_manager)
		)
		return
	
	lat = user_data["lat"]
	lon = user_data["lon"]
	
	# Create qibla finder URL
	qibla_url = QIBLA_FINDER_URL.format(lat=lat, lon=lon)
	
	# Create inline keyboard with qibla finder button
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(
				text=get_text(user_id, "qibla_direction_button"),
				web_app=WebAppInfo(url=qibla_url)
			)]
		]
	)
	
	await message.answer(
		get_text(user_id, "qibla_direction_message"),
		parse_mode="HTML",
		reply_markup=keyboard
	)

# Location settings command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("location_settings"))
async def location_settings_command(message: types.Message):
	"""Handle location settings command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await message.answer(
		get_text(user_id, "location_settings_message"),
		parse_mode="HTML",
		reply_markup=create_location_keyboard(lang, lang_manager)
	)

# Organ command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("organ"))
async def organ_command(message: types.Message):
	"""Handle organ command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await message.answer(
		get_text(user_id, "organ_message"),
		parse_mode="HTML",
		reply_markup=create_organ_keyboard(lang, lang_manager)
	)

# Help command handler - accepts command in any language
@dp.message(lambda message: message.text in get_command_variants("help"))
async def help_command(message: types.Message):
	"""Handle help command"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await message.answer(
		get_text(user_id, "help"),
		reply_markup=create_help_keyboard(lang, lang_manager)
	)

# Add a handler for admin commands
@dp.message(Command("admin"))
async def admin_command(message: types.Message):
	"""Handle admin command"""
	try:
		user_id = message.from_user.id
		
		# Check if user is admin
		if user_id != ADMIN_ID:
			await message.answer(get_text(user_id, "admin_only"))
			return
		
		# Send admin panel
		await message.answer(
			"🛠 <b>Admin panel</b>\n\nQuyidagi amallardan birini tanlang:",
			parse_mode="HTML",
			reply_markup=create_admin_keyboard("uz", lang_manager)  # Admin panel only in Uzbek
		)
	except Exception as e:
		logging.error(f"Error in admin command: {e}")
		await message.answer(f"Error: {e}")

# Add the location handler after the help_command handler
@dp.message(lambda message: message.location is not None)
async def handle_location(message: types.Message):
	"""Handle location message"""
	user_id = message.from_user.id
	
	# Check if user is a member of the required channel
	if not await check_membership(user_id):
		await send_join_channel_message(user_id)
		return
	
	lat = message.location.latitude
	lon = message.location.longitude
	
	# Get user data to preserve language setting before making API call
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN  # Default language
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Get city name from coordinates using reverse geocoding
	try:
		url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=10&accept-language=uz"
		response = requests.get(url, headers={"User-Agent": "TelegramBot"})
		
		if response.status_code == 200:
			data = response.json()
			
			# Try to get city name from address
			address = data.get("address", {})
			city = address.get("city") or address.get("town") or address.get("village") or address.get(
				"county") or "Unknown"
			
			# Save user data
			save_user_data(
				user_id=user_id,
				username=message.from_user.username or "",
				full_name=message.from_user.full_name,
				city=city,
				lat=str(lat),
				lon=str(lon),
				lang=lang
			)
			
			await message.answer(
				f"{get_text(user_id, 'location_saved')}\n"
				f"{get_text(user_id, 'city', city=city)}",
				reply_markup=create_main_keyboard(lang, lang_manager)
			)
			
			# Try to get prayer times for the new location
			prayer_times = await get_prayer_times_namozvaqti(city)
			api_source = "namozvaqti.uz"
			
			# If that fails, use aladhan.com as backup
			if not prayer_times:
				prayer_times = await get_prayer_times_aladhan(lat, lon)
				api_source = "aladhan.com"
			
			if prayer_times:
				text = await format_prayer_times_message(prayer_times, city, user_id, api_source)
				
				# Create inline keyboard
				mosque_button = InlineKeyboardButton(
					text=get_text(user_id, "nearby_mosques"),
					web_app=WebAppInfo(url=f"https://www.google.com/maps/search/Mosques/@{lat},{lon},16z")
				)
				coder_btn = InlineKeyboardButton(
					text=get_text(user_id, "developer"),
					web_app=WebAppInfo(url=f"https://roobotmee.uz")
				)
				taklif = InlineKeyboardButton(
					text=get_text(user_id, "taklif"),
					url="https://t.me/roobotmee"
				)
				quran_button = InlineKeyboardButton(text=get_text(user_id, "quran"), callback_data="quran")
				help_button = InlineKeyboardButton(text=get_text(user_id, "help"), callback_data="help")
				
				# Create the keyboard with inline_keyboard parameter
				keyboard = InlineKeyboardMarkup(inline_keyboard=[
					[mosque_button],
					[quran_button],
					[coder_btn],
					[taklif]
				])
				
				await message.answer(text, parse_mode="HTML", reply_markup=keyboard)
		else:
			await message.answer(
				get_text(user_id, "location_error"),
				reply_markup=create_location_keyboard(lang, lang_manager)
			)
	except Exception as e:
		logging.error(f"Error handling location: {e}")
		await message.answer(
			get_text(user_id, "location_error"),
			reply_markup=create_location_keyboard(lang, lang_manager)
		)

@dp.callback_query(lambda c: c.data == "quran")
async def quran_callback(callback_query: types.CallbackQuery):
	"""Handle quran callback"""
	user_id = callback_query.from_user.id
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "quran_title"),
		parse_mode="HTML",
		reply_markup=create_quran_keyboard(page=1, lang_code=lang, lang_manager=lang_manager)
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("quran_page_"))
async def quran_page_callback(callback_query: types.CallbackQuery):
	"""Handle quran page callback"""
	user_id = callback_query.from_user.id
	page = int(callback_query.data.split("_")[2])
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await bot.edit_message_reply_markup(
		chat_id=user_id,
		message_id=callback_query.message.message_id,
		reply_markup=create_quran_keyboard(page=page, lang_code=lang, lang_manager=lang_manager)
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data == "quran_info")
async def quran_info_callback(callback_query: types.CallbackQuery):
	"""Handle quran info callback"""
	user_id = callback_query.from_user.id
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "quran_info"),
		parse_mode="HTML"
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("quran_") and not c.data.startswith(
	"quran_page_") and c.data != "quran_info" and c.data != "quran_back")
async def quran_surah_callback(callback_query: types.CallbackQuery):
	"""Handle quran surah callback"""
	from quron_data import QURAN_SURAHS, QURAN_SURAH_LINKS
	
	user_id = callback_query.from_user.id
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Get surah number
	surah_number = int(callback_query.data.split("_")[1])
	
	# Find surah data
	surah = None
	for s in QURAN_SURAHS:
		if s["number"] == surah_number:
			surah = s
			break
	
	if not surah:
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "quran_error")
		)
		return
	
	# Get surah link
	link = QURAN_SURAH_LINKS.get(surah_number, "")
	
	# Send surah info
	text = get_text(
		user_id,
		"quran_surah",
		number=surah["number"],
		name=surah["name"],
		name_uz=surah["name_uz"],
		verses=surah["verses"],
		link=link
	)
	
	# Create back button
	back_button = InlineKeyboardButton(
		text=get_text(user_id, "back"),
		callback_data="quran"
	)
	
	keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
	
	await bot.send_message(
		chat_id=user_id,
		text=text,
		parse_mode="HTML",
		reply_markup=keyboard
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data == "quran_back")
async def quran_back_callback(callback_query: types.CallbackQuery):
	"""Handle quran back callback"""
	user_id = callback_query.from_user.id
	
	await quran_callback(callback_query)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data == "help")
async def help_callback(callback_query: types.CallbackQuery):
	"""Handle help callback"""
	user_id = callback_query.from_user.id
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Create help keyboard
	keyboard = create_help_keyboard(lang, lang_manager)
	
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "help"),
		reply_markup=keyboard
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("help_"))
async def help_section_callback(callback_query: types.CallbackQuery):
	"""Handle help section callbacks"""
	user_id = callback_query.from_user.id
	section = callback_query.data.split("_")[1]
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Get the appropriate help text based on the section
	if section == "prayer":
		text = get_text(user_id, "help_prayer_text")
	elif section == "bot":
		text = get_text(user_id, "help_bot_text",
		                version=BOT_VERSION,
		                created=BOT_CREATED_DATE,
		                updated=BOT_LAST_UPDATED)
	elif section == "sources":
		text = get_text(user_id, "help_sources_text")
	elif section == "resources":
		text = get_text(user_id, "help_resources_text")
	else:
		text = get_text(user_id, "unknown_command")
	
	# Create back button
	back_button = InlineKeyboardButton(
		text=get_text(user_id, "back"),
		callback_data="help"
	)
	
	keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
	
	await bot.send_message(
		chat_id=user_id,
		text=text,
		parse_mode="HTML",
		reply_markup=keyboard
	)
	
	# Answer callback query
	await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith("organ_"))
async def organ_callback(callback_query: types.CallbackQuery):
	"""Handle organ callbacks"""
	user_id = callback_query.from_user.id
	action = callback_query.data.split("_")[1]
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN  # Default to Uzbek Latin
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Create back button for all organ features
	back_button = InlineKeyboardButton(
		text=get_text(user_id, "back"),
		callback_data="organ_back"
	)
	
	if action == "back":
		# Return to main menu
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "main_menu"),
			reply_markup=create_main_keyboard(lang, lang_manager)
		)
	elif action == "hadith":
		# Handle hadith and prayers
		hadith = get_random_hadith()
		
		# Create refresh button for new hadith
		refresh_button = InlineKeyboardButton(
			text=get_text(user_id, "new_hadith"),
			callback_data="organ_hadith"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[refresh_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "hadith_title",
			              text=hadith["text"],
			              source=hadith["source"]),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "ramadan":
		# Handle Ramadan calendar
		if not user_data:
			# If no location data, ask for location
			await bot.send_message(
				chat_id=user_id,
				text=get_text(user_id, "location_not_found"),
				reply_markup=create_location_keyboard(lang, lang_manager)
			)
			return
		
		# Get current date
		now = get_current_time_uz()
		today_date = now.strftime("%d.%m.%Y")
		
		# Get Ramadan info for user's location
		city = user_data["city"]
		lat = user_data["lat"]
		lon = user_data["lon"]
		
		# Get prayer times for today
		prayer_times = await get_prayer_times_namozvaqti(city)
		if not prayer_times:
			prayer_times = await get_prayer_times_aladhan(lat, lon)
		
		if prayer_times:
			# Convert to Hijri date (approximate)
			hijri_date = get_hijri_date(now)
			
			# Create monthly calendar button
			calendar_button = InlineKeyboardButton(
				text=get_text(user_id, "monthly_calendar"),
				callback_data="organ_ramadan_monthly"
			)
			
			keyboard = InlineKeyboardMarkup(inline_keyboard=[
				[calendar_button],
				[back_button]
			])
			
			await bot.send_message(
				chat_id=user_id,
				text=get_text(user_id, "ramadan_title",
				              city=city,
				              date=today_date,
				              hijri_date=hijri_date,
				              sahur=prayer_times["fajr"],
				              iftar=prayer_times["maghrib"]),
				parse_mode="HTML",
				reply_markup=keyboard
			)
		else:
			await bot.send_message(
				chat_id=user_id,
				text=get_text(user_id, "error_prayer_times"),
				reply_markup=InlineKeyboardMarkup(inline_keyboard=[[back_button]])
			)
	elif action == "names":
		# Handle Islamic names
		# Show categories first
		boy_button = InlineKeyboardButton(
			text="👦 " + get_text(user_id, "boy_names"),
			callback_data="organ_names_boy"
		)
		girl_button = InlineKeyboardButton(
			text="👧 " + get_text(user_id, "girl_names"),
			callback_data="organ_names_girl"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[boy_button],
			[girl_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "names_title"),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "qibla":
		# Handle Qibla view
		if not user_data:
			# If no location data, ask for location
			await bot.send_message(
				chat_id=user_id,
				text=get_text(user_id, "location_not_found"),
				reply_markup=create_location_keyboard(lang, lang_manager)
			)
			return
		
		lat = user_data["lat"]
		lon = user_data["lon"]
		
		# Create qibla finder URL
		qibla_url = QIBLA_FINDER_URL.format(lat=lat, lon=lon)
		
		# Create qibla finder button
		qibla_button = InlineKeyboardButton(
			text=get_text(user_id, "qibla_direction_button"),
			web_app=WebAppInfo(url=qibla_url)
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[qibla_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "qibla_direction_message"),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "dhikr":
		# Handle Dhikr and salawat - simplified without categories
		# Get random dhikr
		dhikr = get_random_dhikr()
		
		# Create refresh button for new dhikr
		refresh_button = InlineKeyboardButton(
			text=get_text(user_id, "new_dhikr"),
			callback_data="organ_dhikr"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[refresh_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "dhikr_title",
			              arabic=dhikr["arabic"],
			              translation=dhikr["translation"],
			              transliteration=dhikr["transliteration"],
			              virtue=dhikr["virtue"]),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "audio_quran":
		# Handle Audio Quran - go directly to Mishary Rashid's recitations
		# Get popular surahs for quick access
		fatiha_button = InlineKeyboardButton(
			text="1. Al-Fatiha",
			url=get_audio_quran_link("mishary", 1)
		)
		yasin_button = InlineKeyboardButton(
			text="36. Ya-Sin",
			url=get_audio_quran_link("mishary", 36)
		)
		rahman_button = InlineKeyboardButton(
			text="55. Ar-Rahman",
			url=get_audio_quran_link("mishary", 55)
		)
		mulk_button = InlineKeyboardButton(
			text="67. Al-Mulk",
			url=get_audio_quran_link("mishary", 67)
		)
		ikhlas_button = InlineKeyboardButton(
			text="112. Al-Ikhlas",
			url=get_audio_quran_link("mishary", 112)
		)
		
		# Create button to view all surahs
		all_surahs_button = InlineKeyboardButton(
			text=get_text(user_id, "all_surahs"),
			callback_data="organ_audio_mishary_all"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[fatiha_button],
			[yasin_button],
			[rahman_button],
			[mulk_button],
			[ikhlas_button],
			[all_surahs_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "audio_quran_reciter", reciter="Mishary Rashid Alafasy"),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "tahajjud":
		# Handle Tahajjud prayer
		# Create buttons for different sections
		how_to_button = InlineKeyboardButton(
			text=get_text(user_id, "tahajjud_how_to"),
			callback_data="organ_tahajjud_how"
		)
		virtues_button = InlineKeyboardButton(
			text=get_text(user_id, "tahajjud_virtues"),
			callback_data="organ_tahajjud_virtues"
		)
		times_button = InlineKeyboardButton(
			text=get_text(user_id, "tahajjud_times"),
			callback_data="organ_tahajjud_times"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[how_to_button],
			[virtues_button],
			[times_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "tahajjud_title"),
			parse_mode="HTML",
			reply_markup=keyboard
		)
	elif action == "holidays":
		# Handle Islamic holidays
		# Get current year
		current_year = get_current_time_uz().year
		
		# Get Islamic holidays for current year
		holidays = get_islamic_holidays(current_year)
		
		# Create calendar button
		calendar_button = InlineKeyboardButton(
			text=get_text(user_id, "holidays_calendar"),
			callback_data="organ_holidays_calendar"
		)
		
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[calendar_button],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "holidays_title") + "\n\n" + holidays,
			parse_mode="HTML",
			reply_markup=keyboard
		)
	else:
		# For other organ features that are not yet implemented
		keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_button]])
		
		await bot.send_message(
			chat_id=user_id,
			text=get_text(user_id, "feature_coming_soon"),
			reply_markup=keyboard
		)
	
	# Answer callback query
	await callback_query.answer()

# Remove the dhikr categories callback handler
# @dp.callback_query(lambda c: c.data == "organ_dhikr_categories")
# async def dhikr_categories_callback(callback_query: types.CallbackQuery):
#     ...

# Remove the specific dhikr category callback handler
# @dp.callback_query(lambda c: c.data.startswith("organ_dhikr_") and c.data != "organ_dhikr_categories")
# async def dhikr_specific_callback(callback_query: types.CallbackQuery):
#     ...

# Modify the audio_quran_callback to handle only the all_surahs option
@dp.callback_query(lambda c: c.data.startswith("organ_audio_"))
async def audio_quran_callback(callback_query: types.CallbackQuery):
	"""Handle audio quran callback"""
	user_id = callback_query.from_user.id
	action = callback_query.data.split("_")[2]
	
	user_data = get_user_data(user_id)
	lang = LANG_UZ_LATIN
	if user_data and "lang" in user_data:
		lang = user_data["lang"]
	
	# Create back button
	back_button = InlineKeyboardButton(
		text=get_text(user_id, "back"),
		callback_data="organ_audio_quran"
	)
	
	# Handle the all_surahs option
	if action == "mishary" and callback_query.data.endswith("_all"):
		# Create a keyboard with all surahs (or paginated)
		# This is a simplified version - in a real implementation, you would paginate
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="1. Al-Fatiha", url=get_audio_quran_link("mishary", 1))],
			[InlineKeyboardButton(text="2. Al-Baqarah", url=get_audio_quran_link("mishary", 2))],
			[InlineKeyboardButton(text="3. Aal-Imran", url=get_audio_quran_link("mishary", 3))],
			[InlineKeyboardButton(text="4. An-Nisa", url=get_audio_quran_link("mishary", 4))],
			[InlineKeyboardButton(text="5. Al-Ma'idah", url=get_audio_quran_link("mishary", 5))],
			[back_button]
		])
		
		await bot.send_message(
			chat_id=user_id,
			text="📚 <b>Barcha suralar</b>",
			parse_mode="HTML",
			reply_markup=keyboard
		)
	
	# Answer callback query
	await callback_query.answer()

# Admin panel handlers
@dp.message(lambda message: message.text == "📊 Statistika" and message.from_user.id == ADMIN_ID)
async def statistics_command(message: types.Message):
	"""Handle statistics command"""
	try:
		# Only allow admin to access
		if message.from_user.id != ADMIN_ID:
			await message.answer("Bu buyruq faqat admin uchun.")
			return
		
		# Get all users
		users = get_all_users()
		
		# Count users by city
		cities = {}
		for user in users:
			city = user["city"]
			if city in cities:
				cities[city] += 1
			else:
				cities[city] = 1
		
		# Sort cities by count
		sorted_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)
		top_cities = sorted_cities[:10]
		
		# Format top cities
		cities_text = ""
		for i, (city, count) in enumerate(top_cities, 1):
			cities_text += f"{i}. {city}: {count} foydalanuvchi\n"
		
		# Get current date
		now = get_current_time_uz()
		today_date = now.strftime("%d.%m.%Y")
		
		# Send statistics
		await message.answer(
			f"📊 <b>Bot statistikasi</b>\n\n"
			f"📅 <b>Sana:</b> {today_date}\n"
			f"👥 <b>Foydalanuvchilar soni:</b> {len(users)}\n\n"
			f"🏙 <b>Top 10 shaharlar:</b>\n{cities_text}",
			parse_mode="HTML"
		)
	except Exception as e:
		logging.error(f"Error in statistics command: {e}")
		await message.answer(f"Xatolik: {e}")

@dp.message(lambda message: message.text == "📢 Xabar yuborish" and message.from_user.id == ADMIN_ID)
async def broadcast_command(message: types.Message, state: FSMContext):
	"""Handle broadcast message command"""
	try:
		# Only allow admin to access
		if message.from_user.id != ADMIN_ID:
			await message.answer("Bu buyruq faqat admin uchun.")
			return
		
		# Set state to waiting for broadcast message
		await state.set_state(AdminStates.waiting_for_broadcast)
		
		await message.answer(
			"📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:\n\n"
			"<i>Xabarni bekor qilish uchun /cancel buyrug'ini yuboring</i>",
			parse_mode="HTML",
			reply_markup=create_cancel_keyboard("uz", None)  # Cancel keyboard in Uzbek
		)
	except Exception as e:
		logging.error(f"Error in broadcast command: {e}")
		await message.answer(f"Xatolik: {e}")

@dp.message(lambda message: message.from_user.id == ADMIN_ID, AdminStates.waiting_for_broadcast)
async def process_broadcast_message(message: types.Message, state: FSMContext):
	"""Process broadcast message"""
	try:
		# Check if message is empty
		if not message.text or message.text == "/cancel":
			await state.clear()
			await message.answer(
				"✅ Amal bekor qilindi.",
				reply_markup=create_admin_keyboard("uz", None)
			)
			return
		
		# Send confirmation message
		await message.answer("📤 Xabar yuborilmoqda...")
		
		# Broadcast message to all users
		sent_count, failed_count = await broadcast_message_to_all(message.text, "HTML")
		
		# Send result
		await message.answer(
			f"✅ Xabar yuborildi!\n\n"
			f"📊 Statistika:\n"
			f"- Yuborilgan: {sent_count}\n"
			f"- Yuborilmagan: {failed_count}",
			reply_markup=create_admin_keyboard("uz", None)
		)
		
		# Clear state
		await state.clear()
	except Exception as e:
		logging.error(f"Error in process broadcast message: {e}")
		await message.answer(f"Xatolik: {e}")
		await state.clear()

@dp.message(lambda message: message.text == "📣 Majburiy kanal" and message.from_user.id == ADMIN_ID)
async def required_channel_command(message: types.Message, state: FSMContext):
	"""Handle required channel command"""
	try:
		# Only allow admin to access
		if message.from_user.id != ADMIN_ID:
			await message.answer("Bu buyruq faqat admin uchun.")
			return
		
		# Set state to waiting for channel
		await state.set_state(AdminStates.waiting_for_channel)
		
		await message.answer(
			"📣 <b>Majburiy kanal qo'shish</b>\n\n"
			"Iltimos, quyidagi usullardan birini tanlang:\n\n"
			"1. Kanaldan xabarni forward qiling\n"
			"2. Kanal usernameni yuboring (masalan: @kanalquron)\n\n"
			"<i>Eslatma: Bot kanalda admin bo'lishi kerak!</i>\n\n"
			"<i>Bekor qilish uchun /cancel buyrug'ini yuboring</i>",
			parse_mode="HTML",
			reply_markup=create_cancel_keyboard("uz", None)
		)
	except Exception as e:
		logging.error(f"Error in required channel command: {e}")
		await message.answer(f"Xatolik: {e}")

@dp.message(lambda message: message.from_user.id == ADMIN_ID, AdminStates.waiting_for_channel)
async def process_channel_message(message: types.Message, state: FSMContext):
	"""Process channel message"""
	try:
		# Check if message is cancel
		if message.text == "/cancel":
			await state.clear()
			await message.answer(
				"✅ Amal bekor qilindi.",
				reply_markup=create_admin_keyboard("uz", None)
			)
			return
		
		# Check if message is forwarded from channel
		if message.forward_from_chat and message.forward_from_chat.type == "channel":
			channel_id = message.forward_from_chat.id
			channel_name = message.forward_from_chat.title
			
			# Try to get channel link
			try:
				chat = await bot.get_chat(channel_id)
				if chat.invite_link:
					channel_link = chat.invite_link
				else:
					# Ask for manual link
					await message.answer(
						"❌ Kanalda ochiq havola mavjud emas. Iltimos, kanal havolasini qo'lda kiriting:"
					)
					return
			except Exception as e:
				# Ask for manual link
				await message.answer(
					f"❌ Kanal havolasini olishda xatolik: {e}\n"
					f"Iltimos, kanal havolasini qo'lda kiriting:"
				)
				return
		
		# Check if message is channel username
		elif message.text and message.text.startswith("@"):
			channel_username = message.text.strip()
			
			# Try to get channel info
			try:
				chat = await bot.get_chat(channel_username)
				channel_id = chat.id
				channel_name = chat.title
				
				if chat.invite_link:
					channel_link = chat.invite_link
				elif chat.username:
					channel_link = f"https://t.me/{chat.username}"
				else:
					# Ask for manual link
					await message.answer(
						"❌ Kanalda ochiq havola mavjud emas. Iltimos, kanal havolasini qo'lda kiriting:"
					)
					return
			except Exception as e:
				await message.answer(
					f"❌ Kanalni tekshirishda xatolik yuz berdi: {e}\n"
					f"Iltimos, kanal mavjudligini va bot unga qo'shilganligini tekshiring."
				)
				return
		
		# Check if message is channel link
		elif message.text and (message.text.startswith("https://t.me/") or message.text.startswith("t.me/")):
			# Get channel username from link
			channel_username = message.text.split("/")[-1].split("?")[0]
			
			# Try to get channel info
			try:
				chat = await bot.get_chat(f"@{channel_username}")
				channel_id = chat.id
				channel_name = chat.title
				channel_link = message.text
			except Exception as e:
				await message.answer(
					f"❌ Kanalni tekshirishda xatolik yuz berdi: {e}\n"
					f"Iltimos, kanal mavjudligini va bot unga qo'shilganligini tekshiring."
				)
				return
		
		# Invalid format
		else:
			await message.answer(
				"❌ Noto'g'ri format. Iltimos, kanaldan xabarni forward qiling yoki kanal usernameni yuboring."
			)
			return
		
		# Check if bot is admin in the channel
		try:
			bot_member = await bot.get_chat_member(channel_id, (await bot.get_me()).id)
			if bot_member.status not in ["administrator", "creator"]:
				await message.answer(
					"❌ Bot kanalda admin emas. Iltimos, botni kanalga admin qiling va qayta urinib ko'ring."
				)
				return
		except Exception as e:
			await message.answer(
				f"❌ Kanalni tekshirishda xatolik yuz berdi: {e}\n"
				f"Iltimos, kanal mavjudligini va bot unga qo'shilganligini tekshiring."
			)
			return
		
		# Save channel info
		if save_required_channel(channel_id, channel_name, channel_link):
			await message.answer(
				f"✅ Majburiy kanal muvaffaqiyatli qo'shildi!\n\n"
				f"Kanal: {channel_name}\n"
				f"ID: {channel_id}\n"
				f"Link: {channel_link}",
				reply_markup=create_admin_keyboard("uz", None)
			)
		else:
			await message.answer(
				"❌ Majburiy kanalni saqlashda xatolik yuz berdi.",
				reply_markup=create_admin_keyboard("uz", None)
			)
		
		# Clear state
		await state.clear()
	except Exception as e:
		logging.error(f"Error in process channel message: {e}")
		await message.answer(f"Xatolik: {e}")
		await state.clear()

@dp.message(lambda message: message.text == "🔄 Kanalni o'chirish" and message.from_user.id == ADMIN_ID)
async def delete_channel_command(message: types.Message):
	"""Handle delete channel command"""
	try:
		# Only allow admin to access
		if message.from_user.id != ADMIN_ID:
			await message.answer("Bu buyruq faqat admin uchun.")
			return
		
		# Delete required channel
		if delete_required_channel():
			await message.answer(
				"✅ Majburiy kanal o'chirildi.",
				reply_markup=create_admin_keyboard("uz", None)
			)
		else:
			await message.answer(
				"❌ Majburiy kanal topilmadi yoki o'chirishda xatolik yuz berdi.",
				reply_markup=create_admin_keyboard("uz", None)
			)
	except Exception as e:
		logging.error(f"Error in delete channel command: {e}")
		await message.answer(f"Xatolik: {e}")

@dp.message(lambda message: message.text == "🔙 Orqaga" and message.from_user.id == ADMIN_ID)
async def back_to_main_command(message: types.Message):
	"""Handle back to main menu command"""
	try:
		# Only allow admin to access
		if message.from_user.id != ADMIN_ID:
			await message.answer("Bu buyruq faqat admin uchun.")
			return
		
		# Send main menu
		await message.answer(
			"Asosiy menyu",
			reply_markup=create_main_keyboard("uz", None)  # Main menu in Uzbek
		)
	except Exception as e:
		logging.error(f"Error in back to main command: {e}")
		await message.answer(f"Xatolik: {e}")

@dp.message(Command("cancel"))
async def cancel_command_handler(message: types.Message, state: FSMContext):
	"""Handle cancel command"""
	try:
		# Get current state
		current_state = await state.get_state()
		
		if current_state is None:
			await message.answer(
				"❓ Hech qanday amal bajarilmayapti.",
				reply_markup=create_admin_keyboard("uz", None)
			)
			return
		
		# Cancel state
		await state.clear()
		
		await message.answer(
			"✅ Amal bekor qilindi.",
			reply_markup=create_admin_keyboard("uz", None)
		)
	except Exception as e:
		logging.error(f"Error in cancel command: {e}")
		await message.answer(f"Xatolik: {e}")

# Main function to start the bot
async def main():
	try:
		# Log bot startup
		logging.info(f"Starting bot with token: {TOKEN[:5]}...")
		print(f"Starting bot with token: {TOKEN[:5]}...")
		
		# Start the scheduler in the background
		asyncio.create_task(scheduler())
		
		# Start polling with a restart handler
		logging.info("Starting polling...")
		print("Starting polling...")
		await dp.start_polling(bot, skip_updates=False)
	except Exception as e:
		logging.error(f"Error in main function: {e}")
		print(f"ERROR: {e}")
		raise

if __name__ == "__main__":
	try:
		print("Starting the bot...")
		asyncio.run(main())
	except (KeyboardInterrupt, SystemExit):
		print("Bot stopped!")
	except Exception as e:
		print(f"Fatal error: {e}")
		logging.critical(f"Fatal error: {e}", exc_info=True)
		sys.exit(1)

def create_organ_keyboard(lang_code=None, lang_manager=None):
	"""Create the organ features keyboard with text in the specified language"""
	# Default texts if language manager is not provided
	hadith_text = "📜 Hadis va duolar"
	ramadan_text = "🌙 Ramazon taqvimi"
	qibla_text = "🧭 Qibla ko'rinishi"
	names_text = "👶 Islomiy ismlar"
	# Remove the qa_text line
	dhikr_text = "📿 Zikr va salovatlar"
	audio_quran_text = "🎧 Audio Qur'on"
	tahajjud_text = "⏰ Tahajjud namozi"
	holidays_text = "📅 Islomiy bayramlar"
	back_text = "🔙 Orqaga"
	
	# If language manager and code are provided, get translated texts
	if lang_manager and lang_code:
		hadith_text = "📜 " + lang_manager.get_text(lang_code, "hadith_and_prayers")
		ramadan_text = "🌙 " + lang_manager.get_text(lang_code, "ramadan_calendar")
		qibla_text = "🧭 " + lang_manager.get_text(lang_code, "qibla_view")
		names_text = "👶 " + lang_manager.get_text(lang_code, "islamic_names")
		# Remove the qa_text line
		dhikr_text = "📿 " + lang_manager.get_text(lang_code, "dhikr_and_salawat")
		audio_quran_text = "🎧 " + lang_manager.get_text(lang_code, "audio_quran")
		tahajjud_text = "⏰ " + lang_manager.get_text(lang_code, "tahajjud_prayer")
		holidays_text = "📅 " + lang_manager.get_text(lang_code, "islamic_holidays")
		back_text = "🔙 " + lang_manager.get_text(lang_code, "back")
	
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text=hadith_text, callback_data="organ_hadith")],
			[InlineKeyboardButton(text=ramadan_text, callback_data="organ_ramadan")],
			[InlineKeyboardButton(text=qibla_text, callback_data="organ_qibla")],
			[InlineKeyboardButton(text=names_text, callback_data="organ_names")],
			# Remove the qa button line
			[InlineKeyboardButton(text=dhikr_text, callback_data="organ_dhikr")],
			[InlineKeyboardButton(text=audio_quran_text, callback_data="organ_audio_quran")],
			[InlineKeyboardButton(text=tahajjud_text, callback_data="organ_tahajjud")],
			[InlineKeyboardButton(text=holidays_text, callback_data="organ_holidays")],
			[InlineKeyboardButton(text=back_text, callback_data="organ_back")]
		]
	)
	return keyboard

# Cancel state


# Main function to start the bot
async def main():
	try:
		# Log bot startup
		logging.info(f"Starting bot with token: {TOKEN[:5]}...")
		print(f"Starting bot with token: {TOKEN[:5]}...")
		
		# Start the scheduler in the background
		asyncio.create_task(scheduler())
		
		# Start polling with a restart handler
		logging.info("Starting polling...")
		print("Starting polling...")
		await dp.start_polling(bot, skip_updates=False)
	except Exception as e:
		logging.error(f"Error in main function: {e}")
		print(f"ERROR: {e}")
		raise
