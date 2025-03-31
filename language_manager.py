import os
import logging
import importlib

# Define language codes
LANG_UZ_LATIN = "uz"
LANG_UZ_CYRILLIC = "uz_cyrl"
LANG_RU = "ru"
LANG_KZ = "kz"
LANG_KG = "kg"

# Default language
DEFAULT_LANGUAGE = LANG_UZ_LATIN

class LanguageManager:
	"""
	Manages translations for the bot across multiple languages.
	Loads translations from separate language files and provides methods to access them.
	"""
	
	
	def __init__(self):
		self.translations = {}
		self.load_translations()
	
	
	def load_translations(self):
		"""Load all translations from separate language modules"""
		try:
			# Import language modules
			from languages import language_uz_latin, language_uz_cyrillic, language_ru, language_kz, language_kg
			
			# Load translations from modules
			self.translations = {
				LANG_UZ_LATIN: language_uz_latin.translations,
				LANG_UZ_CYRILLIC: language_uz_cyrillic.translations,
				LANG_RU: language_ru.translations,
				LANG_KZ: language_kz.translations,
				LANG_KG: language_kg.translations
			}
			
			logging.info("Successfully loaded translations from language modules")
		except Exception as e:
			logging.error(f"Error loading translations from modules: {e}")
			# Load default translations as fallback
			self._load_default_translations()
	
	
	def _load_default_translations(self):
		"""Load default translations if modules cannot be loaded"""
		# Import default translations from the language files
		try:
			from languages.language_uz_latin import translations as uz_translations
			self.translations[LANG_UZ_LATIN] = uz_translations
			logging.info("Loaded default Uzbek Latin translations")
		except Exception as e:
			logging.error(f"Failed to load default translations: {e}")
			# Set empty dictionary as last resort
			self.translations[LANG_UZ_LATIN] = {}
	
	
	def get_text(self, lang_code, key, **kwargs):
		"""
		Get translated text for a specific key in the specified language

		Args:
			lang_code: Language code
			key: Translation key
			**kwargs: Format parameters for the translation

		Returns:
			Translated text, formatted with kwargs if provided
		"""
		# Get the language dictionary, fallback to default if not found
		lang_dict = self.translations.get(lang_code, self.translations.get(DEFAULT_LANGUAGE, {}))
		
		# Get the text, fallback to default language if not found
		text = lang_dict.get(key, self.translations.get(DEFAULT_LANGUAGE, {}).get(key, key))
		
		# Format the text with the provided kwargs
		if kwargs:
			try:
				return text.format(**kwargs)
			except:
				return text
		
		return text
	
	
	def get_nested_text(self, lang_code, parent_key, child_key, default=""):
		"""
		Get translated text from a nested dictionary

		Args:
			lang_code: Language code
			parent_key: Parent key in the translations dictionary
			child_key: Child key in the nested dictionary
			default: Default value if the key is not found

		Returns:
			Translated text from the nested dictionary
		"""
		# Get the language dictionary, fallback to default if not found
		lang_dict = self.translations.get(lang_code, self.translations.get(DEFAULT_LANGUAGE, {}))
		
		# Get the parent dictionary
		parent_dict = lang_dict.get(parent_key, {})
		
		# Get the child value, fallback to default language if not found
		if not parent_dict:
			parent_dict = self.translations.get(DEFAULT_LANGUAGE, {}).get(parent_key, {})
		
		return parent_dict.get(child_key, default)
	
	
	def get_command_variants(self, command_key):
		"""
		Get all language variants of a specific command

		Args:
			command_key: The command key to get variants for

		Returns:
			List of command variants in all languages
		"""
		variants = []
		for lang_code in self.translations:
			command = self.get_text(lang_code, command_key)
			if command and command not in variants:
				variants.append(command)
		return variants

def lang_manager():
	return None