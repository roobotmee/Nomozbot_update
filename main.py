import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

# Import our modules
from prayer_bot import bot, dp, main as prayer_bot_main
from tasbeh_handler import TasbehStates  # Import the tasbeh states and handlers

# Configure logging
logging.basicConfig(
	level=logging.INFO,
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
	handlers=[
		logging.StreamHandler(sys.stdout)
	]
)

# Main function to start the bot
async def main():
	try:
		# Log bot startup
		logging.info("Starting bot...")
		print("Starting bot...")
		
		# Start the scheduler in the background
		asyncio.create_task(prayer_bot_main())
		
		# Start polling
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

