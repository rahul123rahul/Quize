import pymysql

# Configuration matches XAMPP default
DB_CONFIG = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': '',
    'database': 'qcms_db',
    'cursorclass': pymysql.cursors.DictCursor
}

def get_db_connection():
    try:
        return pymysql.connect(**DB_CONFIG)
    except Exception as e:
        print(f"--- DB ERROR: {e} ---")
        return None