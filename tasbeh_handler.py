import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Import necessary functions from other modules
from prayer_bot import bot, dp, get_text, user_data, save_user_data

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Define states for tasbeh counter
class TasbehStates(StatesGroup):
	counting = State()

# Helper function to get user tasbeh count
def get_user_tasbeh_count(user_id):
	user_id_str = str(user_id)
	if user_id_str in user_data and "tasbeh_count" in user_data[user_id_str]:
		return user_data[user_id_str]["tasbeh_count"]
	return 0

# Helper function to update user tasbeh count
def update_user_tasbeh_count(user_id, count):
	user_id_str = str(user_id)
	if user_id_str not in user_data:
		user_data[user_id_str] = {}
	user_data[user_id_str]["tasbeh_count"] = count
	save_user_data()

# Helper function to reset user tasbeh count
def reset_user_tasbeh_count(user_id):
	user_id_str = str(user_id)
	if user_id_str in user_data:
		user_data[user_id_str]["tasbeh_count"] = 0
		save_user_data()

# Organ callback handler for tasbeh
@dp.callback_query(lambda c: c.data == "organ_tasbeh")
async def tasbeh_callback(callback_query: types.CallbackQuery, state: FSMContext):
	"""Handle tasbeh organ callback"""
	user_id = callback_query.from_user.id
	
	# Initialize tasbeh counter
	count = get_user_tasbeh_count(user_id)
	
	# Create inline keyboard for tasbeh
	keyboard = InlineKeyboardMarkup(inline_keyboard=[
		[
			InlineKeyboardButton(text="➕", callback_data="tasbeh_add"),
			InlineKeyboardButton(text="🔄", callback_data="tasbeh_reset"),
			InlineKeyboardButton(text="❌", callback_data="tasbeh_close")
		],
		[InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="organ_back")]
	])
	
	await bot.send_message(
		chat_id=user_id,
		text=get_text(user_id, "tasbeh_message", count=count),
		reply_markup=keyboard,
		parse_mode="HTML"
	)
	
	# Set tasbeh state
	await state.set_state(TasbehStates.counting)
	
	# Answer callback query
	await callback_query.answer()

# Tasbeh callback handler
@dp.callback_query(lambda c: c.data.startswith("tasbeh_"))
async def process_tasbeh_callback(callback_query: types.CallbackQuery, state: FSMContext):
	"""Handle tasbeh callbacks"""
	# First check if we're in the correct state
	current_state = await state.get_state()
	if current_state != TasbehStates.counting.state:
		await callback_query.answer("Please start tasbeh counting first")
		return
	
	user_id = callback_query.from_user.id
	action = callback_query.data.split("_")[1]
	
	if action == "add":
		# Increment counter
		count = get_user_tasbeh_count(user_id) + 1
		update_user_tasbeh_count(user_id, count)
		
		# Update message
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[
				InlineKeyboardButton(text="➕", callback_data="tasbeh_add"),
				InlineKeyboardButton(text="🔄", callback_data="tasbeh_reset"),
				InlineKeyboardButton(text="❌", callback_data="tasbeh_close")
			],
			[InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="organ_back")]
		])
		
		await bot.edit_message_text(
			chat_id=user_id,
			message_id=callback_query.message.message_id,
			text=get_text(user_id, "tasbeh_message", count=count),
			reply_markup=keyboard,
			parse_mode="HTML"
		)
	
	elif action == "reset":
		# Reset counter
		reset_user_tasbeh_count(user_id)
		
		# Update message
		keyboard = InlineKeyboardMarkup(inline_keyboard=[
			[
				InlineKeyboardButton(text="➕", callback_data="tasbeh_add"),
				InlineKeyboardButton(text="🔄", callback_data="tasbeh_reset"),
				InlineKeyboardButton(text="❌", callback_data="tasbeh_close")
			],
			[InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="organ_back")]
		])
		
		await bot.edit_message_text(
			chat_id=user_id,
			message_id=callback_query.message.message_id,
			text=get_text(user_id, "tasbeh_message", count=0),
			reply_markup=keyboard,
			parse_mode="HTML"
		)
	
	elif action == "close":
		# Close tasbeh counter
		await state.clear()
		
		await bot.edit_message_text(
			chat_id=user_id,
			message_id=callback_query.message.message_id,
			text=get_text(user_id, "tasbeh_closed", count=get_user_tasbeh_count(user_id)),
			parse_mode="HTML"
		)
	
	# Answer callback query
	await callback_query.answer()

