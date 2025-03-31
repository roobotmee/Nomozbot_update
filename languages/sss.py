from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from language_manager import LanguageManager, LANG_UZ_LATIN, LANG_UZ_CYRILLIC, LANG_RU, LANG_KZ, LANG_KG, \
	DEFAULT_LANGUAGE

def create_language_keyboard():
	"""Create an inline keyboard for language selection"""
	from language_manager import LANG_UZ_LATIN, LANG_UZ_CYRILLIC, LANG_RU, LANG_KZ, LANG_KG
	
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="🇺🇿 O'zbek (Latin)", callback_data=f"lang_{LANG_UZ_LATIN}")],
			[InlineKeyboardButton(text="🇺🇿 Ўзбек (Кирилл)", callback_data=f"lang_{LANG_UZ_CYRILLIC}")],
			[InlineKeyboardButton(text="🇷🇺 Русский", callback_data=f"lang_{LANG_RU}")],
			[InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data=f"lang_{LANG_KZ}")],
			[InlineKeyboardButton(text="🇰🇬 Кыргызча", callback_data=f"lang_{LANG_KG}")]
		]
	)
	return keyboard

def create_main_keyboard(lang_code, lang_manager):
	"""Create the main keyboard with text in the specified language"""
	return ReplyKeyboardMarkup(
		keyboard=[
			[KeyboardButton(text=lang_manager.get_text(lang_code, "prayer_times"))],
			[KeyboardButton(text=lang_manager.get_text(lang_code, "quran")),
			 KeyboardButton(text=lang_manager.get_text(lang_code, "qibla"))],
			[KeyboardButton(text=lang_manager.get_text(lang_code, "location_settings")),
			 KeyboardButton(text=lang_manager.get_text(lang_code, "organ"))],
			[KeyboardButton(text=lang_manager.get_text(lang_code, "language")),
			 KeyboardButton(text=lang_manager.get_text(lang_code, "help"))]
		],
		resize_keyboard=True
	)

def create_location_keyboard(lang_code, lang_manager):
	"""Create the location keyboard with text in the specified language"""
	return ReplyKeyboardMarkup(
		keyboard=[
			[KeyboardButton(
				text=lang_manager.get_text(lang_code, "send_location"),
				request_location=True
			)],
			[KeyboardButton(text=lang_manager.get_text(lang_code, "cancel"))]
		],
		resize_keyboard=True
	)

def create_admin_keyboard(lang_code, lang_manager):
	"""Create the admin keyboard with text in the specified language"""
	# For admin panel, we'll use fixed Uzbek text as requested
	return ReplyKeyboardMarkup(
		keyboard=[
			[KeyboardButton(text="📊 Statistika"),
			 KeyboardButton(text="📢 Xabar yuborish")],
			[KeyboardButton(text="📣 Majburiy kanal"),
			 KeyboardButton(text="🔄 Kanalni o'chirish")],
			[KeyboardButton(text="🔙 Orqaga")]
		],
		resize_keyboard=True
	)

def create_cancel_keyboard(lang_code, lang_manager):
	"""Create the cancel keyboard with text in the specified language"""
	return ReplyKeyboardMarkup(
		keyboard=[
			[KeyboardButton(text=lang_manager.get_text(lang_code, "cancel"))]
		],
		resize_keyboard=True
	)

def create_help_keyboard(lang_code, lang_manager):
	"""Create the help keyboard with text in the specified language"""
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="🕋 " + lang_manager.get_text(lang_code, "help_prayer"),
			                      callback_data="help_prayer")],
			[InlineKeyboardButton(text="📱 " + lang_manager.get_text(lang_code, "help_bot"),
			                      callback_data="help_bot")],
			[InlineKeyboardButton(text="🔍 " + lang_manager.get_text(lang_code, "help_sources"),
			                      callback_data="help_sources")],
			[InlineKeyboardButton(text="📚 " + lang_manager.get_text(lang_code, "help_resources"),
			                      callback_data="help_resources")],
			[InlineKeyboardButton(ext=lang_manager.get_text(lang_code, "taklif"),
			                      url="https://t.me/roobotmee")],
			[InlineKeyboardButton(text="" + lang_manager.get_text(lang_code, "developer"),
			                      web_app=WebAppInfo(url="https://roobotmee.uz"))]
		]
	
	)

def create_quran_keyboard(page=1, lang_code=None, lang_manager=None):
	"""Create Quran keyboard with pagination and 3 columns"""
	from quron_data import QURAN_SURAHS
	
	# Calculate start and end indices for current page
	items_per_page = 30  # Increased to show more surahs per page
	start_idx = (page - 1) * items_per_page
	end_idx = min(start_idx + items_per_page, len(QURAN_SURAHS))
	
	# Get surahs for current page
	current_surahs = QURAN_SURAHS[start_idx:end_idx]
	
	# Create buttons for each surah in 3 columns
	surah_buttons = []
	row = []
	
	for i, surah in enumerate(current_surahs):
		# Add button to current row
		row.append(
			InlineKeyboardButton(
				text=f"📚 {surah['number']}. {surah['name_uz']}",
				callback_data=f"quran_{surah['number']}"
			)
		)
		
		# After adding 3 buttons or at the end of the list, append the row
		if len(row) == 3 or i == len(current_surahs) - 1:
			surah_buttons.append(row)
			row = []  # Reset row for next set of buttons
	
	# Add navigation buttons
	nav_buttons = []
	
	# Add previous page button if not on first page
	if page > 1:
		prev_text = "⬅️ Oldingi"
		if lang_manager and lang_code:
			prev_text = "⬅️ " + lang_manager.get_text(lang_code, "previous")
		
		nav_buttons.append(
			InlineKeyboardButton(
				text=prev_text,
				callback_data=f"quran_page_{page - 1}"
			)
		)
	
	# Add info button
	info_text = "ℹ️ Info"
	if lang_manager and lang_code:
		info_text = "ℹ️ " + lang_manager.get_text(lang_code, "info")
	
	nav_buttons.append(
		InlineKeyboardButton(
			text=info_text,
			callback_data="quran_info"
		)
	)
	
	# Add next page button if not on last page
	if end_idx < len(QURAN_SURAHS):
		next_text = "Keyingi ➡️"
		if lang_manager and lang_code:
			next_text = lang_manager.get_text(lang_code, "next") + " ➡️"
		
		nav_buttons.append(
			InlineKeyboardButton(
				text=next_text,
				callback_data=f"quran_page_{page + 1}"
			)
		)
	
	# Add back button
	back_text = "🔙 Orqaga"
	if lang_manager and lang_code:
		back_text = "🔙 " + lang_manager.get_text(lang_code, "back")
	
	back_button = [
		InlineKeyboardButton(
			text=back_text,
			callback_data="quran_back"
		)
	]
	
	# Combine all buttons
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=surah_buttons + [nav_buttons] + [back_button]
	)
	
	return keyboard

# Update the create_organ_keyboard function to use 2 columns
def create_organ_keyboard(lang_code=None, lang_manager=None):
	"""Create the organ features keyboard with text in the specified language"""
	# Default texts if language manager is not provided (in Uzbek)
	hadith_text = "📜 Hadislar"
	dhikr_text = "📿 Zikrlar"
	quran_text = "📖 Qur'on"
	dua_text = "🤲 Duolar"
	sadaqa_text = "💰 Sadaqa"
	halal_text = "🍽 Halol"
	namaz_text = "🕋 Namoz"
	ramadan_text = "🌙 Ramazon"
	tasbeh_text = "📿 Tasbeh"
	names_text = "👶 Ismlar"
	holidays_text = "📅 Bayramlar"
	qibla_text = "🧭 Qibla"
	back_text = "🔙 Orqaga"
	
	# If language manager and code are provided, get translated texts
	if lang_manager and lang_code:
		if lang_code == LANG_RU:
			hadith_text = "📜 Хадисы"
			dhikr_text = "📿 Зикры"
			quran_text = "📖 Коран"
			dua_text = "🤲 Дуа"
			sadaqa_text = "💰 Садака"
			halal_text = "🍽 Халяль"
			namaz_text = "🕋 Намаз"
			ramadan_text = "🌙 Рамадан"
			tasbeh_text = "📿 Тасбих"
			names_text = "👶 Имена"
			holidays_text = "📅 Праздники"
			qibla_text = "🧭 Кибла"
			back_text = "🔙 Назад"
		elif lang_code == LANG_UZ_CYRILLIC:
			hadith_text = "📜 Ҳадислар"
			dhikr_text = "📿 Зикрлар"
			quran_text = "📖 Қуръон"
			dua_text = "🤲 Дуолар"
			sadaqa_text = "💰 Садақа"
			halal_text = "🍽 Ҳалол"
			namaz_text = "🕋 Намоз"
			ramadan_text = "🌙 Рамазон"
			tasbeh_text = "📿 Тасбеҳ"
			names_text = "👶 Исмлар"
			holidays_text = "📅 Байрамлар"
			qibla_text = "🧭 Қибла"
			back_text = "🔙 Орқага"
		elif lang_code == LANG_KZ:
			hadith_text = "📜 Хадистер"
			dhikr_text = "📿 Зікірлер"
			quran_text = "📖 Құран"
			dua_text = "🤲 Дұғалар"
			sadaqa_text = "💰 Садақа"
			halal_text = "🍽 Халал"
			namaz_text = "🕋 Намаз"
			ramadan_text = "🌙 Рамазан"
			tasbeh_text = "📿 Тәсбих"
			names_text = "👶 Есімдер"
			holidays_text = "📅 Мейрамдар"
			qibla_text = "🧭 Құбыла"
			back_text = "🔙 Артқа"
		elif lang_code == LANG_KG:
			hadith_text = "📜 Хадистер"
			dhikr_text = "📿 Зикирлер"
			quran_text = "📖 Куран"
			dua_text = "🤲 Дубалар"
			sadaqa_text = "💰 Садака"
			halal_text = "🍽 Халал"
			namaz_text = "🕋 Намаз"
			ramadan_text = "🌙 Рамазан"
			tasbeh_text = "📿 Тасбих"
			names_text = "👶 Ысымдар"
			holidays_text = "📅 Майрамдар"
			qibla_text = "🧭 Кыбыла"
			back_text = "🔙 Артка"
	
	# Create a 2-column layout
	keyboard = InlineKeyboardMarkup(
		inline_keyboard=[
			[
				InlineKeyboardButton(text=hadith_text, callback_data="organ_hadith"),
				InlineKeyboardButton(text=dhikr_text, callback_data="organ_dhikr")
			],
			[
				InlineKeyboardButton(text=quran_text, callback_data="organ_audio_quran"),
				InlineKeyboardButton(text=dua_text, callback_data="organ_dua")
			],
			[
				InlineKeyboardButton(text=sadaqa_text, callback_data="organ_sadaqa"),
				InlineKeyboardButton(text=halal_text, callback_data="organ_halal")
			],
			[
				InlineKeyboardButton(text=namaz_text, callback_data="organ_namaz"),
				InlineKeyboardButton(text=ramadan_text, callback_data="organ_ramadan")
			],
			[
				InlineKeyboardButton(text=tasbeh_text, callback_data="organ_tasbeh"),
				InlineKeyboardButton(text=names_text, callback_data="organ_names")
			],
			[
				InlineKeyboardButton(text=holidays_text, callback_data="organ_holidays"),
				InlineKeyboardButton(text=qibla_text, callback_data="organ_qibla")
			],
			[InlineKeyboardButton(text=back_text, callback_data="organ_back")]
		]
	)
	return keyboard

