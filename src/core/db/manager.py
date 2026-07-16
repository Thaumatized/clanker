import sqlite3
from typing import Optional
from config import CONFIG

# --- Connection Helpers (Moved from clanker.py) ---

def get_db_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def get_profile_db_connection() -> sqlite3.Connection:
    return get_db_connection(f'databases/{CONFIG['profile']}.sqlite') # Use the same helper function

def get_shared_db_connection() -> sqlite3.Connection:
    return get_db_connection('databases/shared.sqlite') # Use the same helper function

# --- State Accessors (High-level API) ---

def is_channel_enabled(channel_id: int) -> bool:
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_enabled FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row['is_enabled'] == 1

def set_channel_enabled(channel_id: int, enabled: bool) -> bool:
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, is_enabled) VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET is_enabled = excluded.is_enabled
    ''', (channel_id, 1 if enabled else 0))
    conn.commit()
    conn.close()
    return enabled

def get_whack(channel_id: int) -> Optional[int]:
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT whack_message_id FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row['whack_message_id'] if row else None

def set_whack(channel_id: int, whack_message_id: int):
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, whack_message_id) VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET whack_message_id = excluded.whack_message_id
    ''', (channel_id, whack_message_id))
    conn.commit()
    conn.close()

def get_history_length(channel_id: int) -> int:
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT history_length FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row['history_length'] if row else 25 # Default value

def set_history_length(channel_id: int, history_length: int):
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, history_length) VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET history_length = excluded.history_length
    ''', (channel_id, history_length))
    conn.commit()
    conn.close()

def get_bot_to_bot(channel_id: int) -> bool:
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT bot_to_bot_enabled FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    return row['bot_to_bot_enabled'] == 1 if row else False

def set_bot_to_bot(channel_id: int, enabled: bool):
    conn = get_shared_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, bot_to_bot_enabled) VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET bot_to_bot_enabled = excluded.bot_to_bot_enabled
    ''', (channel_id, 1 if enabled else 0))
    conn.commit()
    conn.close()

def get_model(channel_id: int) -> dict:
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT model_name FROM channels WHERE channel_id = ?', (channel_id,))
    row = cursor.fetchone()
    conn.close()
    modelname = row['model_name'] if row else CONFIG['base']['models']['default']
    AVAILABLE_MODELS = CONFIG['base']['models']['censored']
    for model in AVAILABLE_MODELS:
        if model['name'] == modelname:
            return model

def set_model(channel_id: int, model: dict):
    conn = get_profile_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO channels (channel_id, model_name) VALUES (?, ?) ON CONFLICT(channel_id) DO UPDATE SET model_name = excluded.model_name
    ''', (channel_id, model['name']))
    conn.commit()
    conn.close()

# Expose a function to initialize all necessary components
def initialize_all_db():
    from .migrations import run_migrations
    run_migrations()