import sqlite3
from config import CONFIG

# Assuming DatabaseConfig is available or passed in, for simplicity we use hardcoded paths here.
PROFILE_DB_PATH = f'databases/{CONFIG['profile']}.sqlite'
SHARED_DB_PATH = 'databases/shared.sqlite'

def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Establishes a connection to the specified SQLite database."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def run_migrations():
    """Runs all necessary migrations for both profile-specific and shared databases."""
    print("--- Running Database Migrations ---")

    # 1. Profile-Specific Database Migration (Clanker's core settings)
    conn = None
    try:
        conn = get_db_connection(PROFILE_DB_PATH)
        cursor = conn.cursor()

        # Robustly add columns to the 'channels' table if they don't exist
        print("-> Migrating profile 'channels' table...")

        # Add history_length
        try:
            cursor.execute('ALTER TABLE channels ADD COLUMN history_length INTEGER DEFAULT 25')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Warning adding history_length: {e}")

        # Add whack_message_id
        try:
            cursor.execute('ALTER TABLE channels ADD COLUMN whack_message_id INTEGER DEFAULT 0')
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Warning adding whack_message_id: {e}")

        # Add model_name
        default_model = f'{CONFIG["base"]["models"]["default"]}'
        try:
            cursor.execute(f"ALTER TABLE channels ADD COLUMN model_name TEXT DEFAULT '{default_model}'")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                print(f"Warning adding model_name: {e}")

        # Ensure the base table structure exists (this is safer than relying on a single CREATE TABLE IF NOT EXISTS)
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS channels (
                channel_id INTEGER PRIMARY KEY,
                is_enabled INTEGER DEFAULT 0,
                history_length INTEGER DEFAULT 25,
                whack_message_id INTEGER DEFAULT 0,
                model_name TEXT DEFAULT '{default_model}'
            )
        ''')

        conn.commit()
    except sqlite3.Error as e:
        print(f"🚨 Error during profile database migration: {e}")
    finally:
        if conn:
            conn.close()

    # 2. Shared Database Migration (Global bot-to-bot settings)
    conn = None
    try:
        conn = get_db_connection(SHARED_DB_PATH)
        cursor = conn.cursor()

        print("-> Migrating shared 'channels' table...")

        # Only add columns if they are genuinely missing in the shared DB context (if applicable)
        # For now, we assume only bot_to_bot_enabled is needed here.
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id INTEGER PRIMARY KEY,
                    bot_to_bot_enabled INTEGER DEFAULT 0
                )
            ''')
        except sqlite3.OperationalError as e:
             if "duplicate column name" not in str(e):
                 print(f"Warning during shared DB migration: {e}")

        conn.commit()
    except sqlite3.Error as e:
        print(f"🚨 Error during shared database migration: {e}")
    finally:
        if conn:
            conn.close()

    print("--- Migrations Complete ---")