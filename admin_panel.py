#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Admin Panel Module for Prayer Times Bot
Handles admin commands and functionality
"""

import asyncio
import logging
import datetime
from typing import Dict, Any, List, Tuple, Optional

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
	format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
	level=logging.INFO
)
logger = logging.getLogger(__name__)

# Default translations for fallback
DEFAULT_TRANSLATIONS = {
	"admin_only": "You are not authorized to use this command.",
	"admin_panel_title": "🛠 <b>Admin Panel</b>\n\nSelect an option:",
	"admin_stats": "📊 Statistics",
	"admin_broadcast": "📢 Broadcast",
	"admin_channel_add": "📣 Add Channel",
	"admin_channel_remove": "🔄 Remove Channel",
	"back_to_main": "🔙 Back to Main Menu",
	"broadcast_instruction": "📢 <b>Broadcast Message</b>\n\nEnter the message you want to broadcast to all users:\n\n<i>Send /cancel to cancel</i>",
	"broadcast_cancelled": "Broadcast cancelled.",
	"broadcast_sending": "📤 Sending broadcast message...",
	"broadcast_result": "✅ Broadcast sent!\n\n📊 Statistics:\n- Sent: {sent}\n- Failed: {failed}",
	"stats_title": "📊 <b>Bot Statistics</b>",
	"stats_date": "📅 <b>Date:</b> {date}",
	"stats_users": "👥 <b>Number of users:</b> {total}",
	"stats_cities": "🏙 <b>Top cities:</b>\n{cities}",
	"stats_languages": "🌐 <b>Languages:</b>\n{languages}",
	"channel_add_instruction": "📣 <b>Add Required Channel</b>\n\nPlease choose one of the following methods:\n\n1. Forward a message from the channel\n2. Send the channel username (e.g., @channelname)\n\n<i>Note: The bot must be an admin in the channel!</i>\n\n<i>Send /cancel to cancel</i>",
	"channel_removed": "✅ Required channel has been removed."
}

def get_admin_keyboard(lang_manager=None, user_id=None):
	"""Create admin keyboard with proper translations"""
	# If language manager and user_id are provided, use them for translations
	if lang_manager and user_id is not None:
		try:
			stats_text = lang_manager.get_text(user_id, "admin_stats")
			broadcast_text = lang_manager.get_text(user_id, "admin_broadcast")
			add_channel_text = lang_manager.get_text(user_id, "admin_channel_add")
			remove_channel_text = lang_manager.get_text(user_id, "admin_channel_remove")
			back_text = lang_manager.get_text(user_id, "back_to_main")
		except (AttributeError, TypeError):
			# Fallback to default translations if there's an error
			stats_text = DEFAULT_TRANSLATIONS["admin_stats"]
			broadcast_text = DEFAULT_TRANSLATIONS["admin_broadcast"]
			add_channel_text = DEFAULT_TRANSLATIONS["admin_channel_add"]
			remove_channel_text = DEFAULT_TRANSLATIONS["admin_channel_remove"]
			back_text = DEFAULT_TRANSLATIONS["back_to_main"]
	else:
		# Use default translations if language manager or user_id is not provided
		stats_text = DEFAULT_TRANSLATIONS["admin_stats"]
		broadcast_text = DEFAULT_TRANSLATIONS["admin_broadcast"]
		add_channel_text = DEFAULT_TRANSLATIONS["admin_channel_add"]
		remove_channel_text = DEFAULT_TRANSLATIONS["admin_channel_remove"]
		back_text = DEFAULT_TRANSLATIONS["back_to_main"]
	
	# Create keyboard with translated buttons
	keyboard = ReplyKeyboardMarkup([
		[stats_text, broadcast_text],
		[add_channel_text, remove_channel_text],
		[back_text]
	], resize_keyboard=True)
	
	return keyboard

def get_cancel_keyboard():
	"""Create a simple cancel keyboard"""
	return ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)

def get_text(key, lang_manager=None, user_id=None, **kwargs):
	"""Get text with proper translation"""
	# If language manager and user_id are provided, use them for translations
	if lang_manager and user_id is not None:
		try:
			return lang_manager.get_text(user_id, key, **kwargs)
		except (AttributeError, TypeError):
			# Fallback to default translations if there's an error
			if key in DEFAULT_TRANSLATIONS:
				text = DEFAULT_TRANSLATIONS[key]
				# Format with kwargs if provided
				if kwargs and isinstance(text, str):
					return text.format(**kwargs)
				return text
			return f"Missing translation: {key}"
	else:
		# Use default translations if language manager or user_id is not provided
		if key in DEFAULT_TRANSLATIONS:
			text = DEFAULT_TRANSLATIONS[key]
			# Format with kwargs if provided
			if kwargs and isinstance(text, str):
				return text.format(**kwargs)
			return text
		return f"Missing translation: {key}"

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, lang_manager=None):
	"""Handle admin command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Show admin panel
	keyboard = get_admin_keyboard(lang_manager, user_id)
	
	await update.message.reply_text(
		get_text("admin_panel_title", lang_manager, user_id),
		reply_markup=keyboard,
		parse_mode=ParseMode.HTML
	)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, lang_manager=None):
	"""Handle broadcast command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Send broadcast instruction
	await update.message.reply_text(
		get_text("broadcast_instruction", lang_manager, user_id),
		parse_mode=ParseMode.HTML,
		reply_markup=get_cancel_keyboard()
	)

async def process_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, user_data_dict: Dict,
                            lang_manager=None):
	"""Process broadcast message"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Get broadcast message
	message = update.message
	
	# Check if message is cancel command
	if message.text and message.text.lower() == "/cancel":
		await update.message.reply_text(
			get_text("broadcast_cancelled", lang_manager, user_id),
			reply_markup=get_admin_keyboard(lang_manager, user_id)
		)
		return
	
	# Send confirmation message
	status_message = await update.message.reply_text(get_text("broadcast_sending", lang_manager, user_id))
	
	# Broadcast message to all users
	sent_count = 0
	failed_count = 0
	total_users = len(user_data_dict)
	processed = 0
	
	# Store message content for reuse
	message_text = message.text if message.text else None
	photo = message.photo[-1].file_id if message.photo else None
	video = message.video.file_id if message.video else None
	document = message.document.file_id if message.document else None
	audio = message.audio.file_id if message.audio else None
	voice = message.voice.file_id if message.voice else None
	caption = message.caption if message.caption else None
	
	# Update status message periodically
	last_update_time = datetime.datetime.now()
	
	for user_id_str, user_data in user_data_dict.items():
		try:
			# Send appropriate message type
			if photo:
				await context.bot.send_photo(
					chat_id=int(user_id_str),
					photo=photo,
					caption=caption,
					parse_mode=ParseMode.HTML
				)
			elif video:
				await context.bot.send_video(
					chat_id=int(user_id_str),
					video=video,
					caption=caption,
					parse_mode=ParseMode.HTML
				)
			elif document:
				await context.bot.send_document(
					chat_id=int(user_id_str),
					document=document,
					caption=caption,
					parse_mode=ParseMode.HTML
				)
			elif audio:
				await context.bot.send_audio(
					chat_id=int(user_id_str),
					audio=audio,
					caption=caption,
					parse_mode=ParseMode.HTML
				)
			elif voice:
				await context.bot.send_voice(
					chat_id=int(user_id_str),
					voice=voice,
					caption=caption,
					parse_mode=ParseMode.HTML
				)
			elif message_text:
				await context.bot.send_message(
					chat_id=int(user_id_str),
					text=message_text,
					parse_mode=ParseMode.HTML
				)
			
			sent_count += 1
			
			# Add a small delay to avoid hitting rate limits
			await asyncio.sleep(0.05)
		
		except Exception as e:
			logger.error(f"Failed to send broadcast to user {user_id_str}: {e}")
			failed_count += 1
		
		processed += 1
		
		# Update status message every 3 seconds or every 50 users
		current_time = datetime.datetime.now()
		if processed % 50 == 0 or (current_time - last_update_time).total_seconds() > 3:
			progress = int((processed / total_users) * 100)
			await status_message.edit_text(
				f"📤 Sending broadcast message... {progress}% complete\n"
				f"✅ Sent: {sent_count}\n"
				f"❌ Failed: {failed_count}\n"
				f"📊 Progress: {processed}/{total_users}"
			)
			last_update_time = current_time
	
	# Send final result
	await status_message.edit_text(
		get_text("broadcast_result", lang_manager, user_id, sent=sent_count, failed=failed_count),
	)
	
	# Return to admin keyboard
	await update.message.reply_text(
		"Broadcast completed.",
		reply_markup=get_admin_keyboard(lang_manager, user_id)
	)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, user_data_dict: Dict,
                        lang_manager=None):
	"""Handle statistics command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Count total users
	total_users = len(user_data_dict)
	
	# Count users by city
	cities = {}
	for user_id_str, user_data in user_data_dict.items():
		city = user_data.get("city", "Unknown")
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
		cities_text += f"{i}. {city}: {count} users\n"
	
	# Count users by language
	languages = {}
	for user_id_str, user_data in user_data_dict.items():
		lang = user_data.get("language", "unknown")
		if lang in languages:
			languages[lang] += 1
		else:
			languages[lang] = 1
	
	# Format language statistics
	lang_stats = "\n".join([f"- {lang}: {count}" for lang, count in languages.items()])
	
	# Get current date
	now = datetime.datetime.now(datetime.timezone.utc)
	today_date = now.strftime("%d.%m.%Y")
	
	# Build statistics message
	stats_message = (
		f"{get_text('stats_title', lang_manager, user_id)}\n\n"
		f"{get_text('stats_date', lang_manager, user_id, date=today_date)}\n"
		f"{get_text('stats_users', lang_manager, user_id, total=total_users)}\n\n"
		f"{get_text('stats_cities', lang_manager, user_id, cities=cities_text)}\n"
		f"{get_text('stats_languages', lang_manager, user_id, languages=lang_stats)}"
	)
	
	# Send statistics
	await update.message.reply_text(
		stats_message,
		parse_mode=ParseMode.HTML
	)

async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, lang_manager=None):
	"""Handle add channel command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Send channel add instruction
	await update.message.reply_text(
		get_text("channel_add_instruction", lang_manager, user_id),
		parse_mode=ParseMode.HTML,
		reply_markup=get_cancel_keyboard()
	)

async def process_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int,
                              required_channels: List, save_data_func, lang_manager=None):
	"""Process channel addition request"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	message = update.message
	channel_id = None
	channel_title = None
	
	# Check if message is cancel command
	if message.text and message.text.lower() == "/cancel":
		await update.message.reply_text(
			get_text("broadcast_cancelled", lang_manager, user_id),
			reply_markup=get_admin_keyboard(lang_manager, user_id)
		)
		return
	
	# Handle forwarded message from channel
	if message.forward_from_chat and message.forward_from_chat.type == "channel":
		channel_id = message.forward_from_chat.id
		channel_title = message.forward_from_chat.title
	
	# Handle channel username
	elif message.text and message.text.startswith("@"):
		channel_username = message.text.strip()
		try:
			# Try to get channel info
			chat = await context.bot.get_chat(channel_username)
			if chat.type == "channel":
				channel_id = chat.id
				channel_title = chat.title
			else:
				await update.message.reply_text(
					"❌ Error: This is not a channel. Please provide a valid channel username.",
					reply_markup=get_cancel_keyboard()
				)
				return
		except Exception as e:
			logger.error(f"Error getting channel info: {e}")
			await update.message.reply_text(
				f"❌ Error: Could not find channel {channel_username}. Make sure the bot is a member of the channel.",
				reply_markup=get_cancel_keyboard()
			)
			return
	
	# Handle channel ID directly
	elif message.text and message.text.strip().startswith("-100"):
		try:
			channel_id = int(message.text.strip())
			chat = await context.bot.get_chat(channel_id)
			if chat.type == "channel":
				channel_title = chat.title
			else:
				await update.message.reply_text(
					"❌ Error: This is not a channel. Please provide a valid channel ID.",
					reply_markup=get_cancel_keyboard()
				)
				return
		except Exception as e:
			logger.error(f"Error getting channel info: {e}")
			await update.message.reply_text(
				f"❌ Error: Could not find channel with ID {message.text}. Make sure the bot is a member of the channel.",
				reply_markup=get_cancel_keyboard()
			)
			return
	
	else:
		await update.message.reply_text(
			"❌ Invalid input. Please forward a message from the channel or send the channel username (e.g., @channelname).",
			reply_markup=get_cancel_keyboard()
		)
		return
	
	# Check if bot is admin in the channel
	try:
		bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
		if bot_member.status not in ["administrator", "creator"]:
			await update.message.reply_text(
				"❌ Error: The bot is not an admin in this channel. Please make the bot an admin first.",
				reply_markup=get_cancel_keyboard()
			)
			return
	except Exception as e:
		logger.error(f"Error checking bot admin status: {e}")
		await update.message.reply_text(
			"❌ Error: Could not verify bot's admin status in the channel. Make sure the bot is an admin.",
			reply_markup=get_cancel_keyboard()
		)
		return
	
	# Check if channel is already in the list
	for channel in required_channels:
		if channel.get("id") == channel_id:
			await update.message.reply_text(
				f"❌ Channel '{channel_title}' is already in the required channels list.",
				reply_markup=get_admin_keyboard(lang_manager, user_id)
			)
			return
	
	# Add channel to required channels list
	channel_info = {
		"id": channel_id,
		"title": channel_title,
		"username": getattr(await context.bot.get_chat(channel_id), "username", None)
	}
	
	required_channels.append(channel_info)
	
	# Save data
	if save_data_func:
		await save_data_func()
	
	# Send confirmation
	await update.message.reply_text(
		f"✅ Channel '{channel_title}' has been added to the required channels list.",
		reply_markup=get_admin_keyboard(lang_manager, user_id)
	)

async def remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int,
                                 required_channels: List, save_data_func, lang_manager=None):
	"""Handle remove channel command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Check if there are any channels to remove
	if not required_channels:
		await update.message.reply_text(
			"❌ There are no required channels to remove.",
			reply_markup=get_admin_keyboard(lang_manager, user_id)
		)
		return
	
	# Create inline keyboard with channels
	keyboard = []
	for i, channel in enumerate(required_channels):
		keyboard.append([
			InlineKeyboardButton(
				f"{i + 1}. {channel.get('title', 'Unknown')}",
				callback_data=f"remove_channel_{i}"
			)
		])
	
	# Add cancel button
	keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="remove_channel_cancel")])
	
	# Send message with channel selection
	await update.message.reply_text(
		"Select a channel to remove:",
		reply_markup=InlineKeyboardMarkup(keyboard)
	)

async def process_remove_channel(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int,
                                 required_channels: List, save_data_func, lang_manager=None):
	"""Process channel removal callback"""
	query = update.callback_query
	await query.answer()
	
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await query.edit_message_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Get callback data
	callback_data = query.data
	
	# Handle cancel
	if callback_data == "remove_channel_cancel":
		await query.edit_message_text(
			"❌ Channel removal cancelled.",
		)
		return
	
	# Get channel index
	try:
		channel_index = int(callback_data.split("_")[-1])
		if 0 <= channel_index < len(required_channels):
			channel = required_channels[channel_index]
			channel_title = channel.get("title", "Unknown")
			
			# Remove channel
			required_channels.pop(channel_index)
			
			# Save data
			if save_data_func:
				await save_data_func()
			
			# Send confirmation
			await query.edit_message_text(
				f"✅ Channel '{channel_title}' has been removed from the required channels list."
			)
		else:
			await query.edit_message_text("❌ Invalid channel selection.")
	except (ValueError, IndexError) as e:
		logger.error(f"Error removing channel: {e}")
		await query.edit_message_text("❌ Error removing channel.")

async def back_to_main_command(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id: int, lang_manager=None):
	"""Handle back to main menu command"""
	user_id = update.effective_user.id
	
	# Check if user is admin
	if user_id != admin_id:
		await update.message.reply_text(get_text("admin_only", lang_manager, user_id))
		return
	
	# Create main menu keyboard
	keyboard = ReplyKeyboardMarkup([
		["🕌 Namoz vaqtlari", "📿 Tasbeh"],
		["📖 Qur'on", "🧭 Qibla"],
		["🌐 Til / Язык", "❓ Yordam"]
	], resize_keyboard=True)
	
	# Send main menu
	await update.message.reply_text(
		"Main Menu",
		reply_markup=keyboard
	)

