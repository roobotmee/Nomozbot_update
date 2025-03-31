# This file ensures all handlers are properly imported and registered with the dispatcher

# Import all handlers
from prayer_bot import dp as prayer_dp
from tasbeh_handler import dp as tasbeh_dp

# Make sure all handlers are registered
def register_all_handlers():
    # This function doesn't need to do anything as the handlers are registered
    # when their modules are imported, but it ensures the imports are not optimized away
    pass

