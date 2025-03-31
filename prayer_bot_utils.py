import json
import os
import logging
from typing import Dict, Any, Optional

# Data file path
USER_DATA_FILE = "users.txt"

# User data structure
user_data: Dict[str, Dict[str, Any]] = {}

# Load user data from file
def load_user_data() -> Dict[str, Dict[str, Any]]:
	global user_data
	try:
		if os.path.exists(USER_DATA_FILE):
			with open(USER_DATA_FILE, "r", encoding="utf-8") as file:
				user_data = json.load(file)
		return user_data
	except Exception as e:
		logging.error(f"Error loading user data: {e}")
		return {}

# Save user data to file
def save_user_data() -> None:
	try:
		with open(USER_DATA_FILE, "w", encoding="utf-8") as file:
			json.dump(user_data, file, ensure_ascii=False, indent=4)
	except Exception as e:
		logging.error(f"Error saving user data: {e}")

# Helper function to get user language
def get_user_language(user_id: int) -> str:
	from language_manager import LANG_UZ_LATIN
	
	user_id_str = str(user_id)
	if user_id_str in user_data and "language" in user_data[user_id_str]:
		return user_data[user_id_str]["language"]
	return LANG_UZ_LATIN  # Default language

# Helper function to get text in user's language
def get_text(user_id: int, key: str, **kwargs) -> str:
	from language_manager import lang_manager
	
	lang_code = get_user_language(user_id)
	return lang_manager.get_text(lang_code, key, **kwargs)

# Initialize user data
user_data = load_user_data()

