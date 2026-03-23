import pymysql
import sys

# Configuration
DB_HOST = "lh510.irandns.com"  # Based on URL from screenshot
DB_NAME = "systemir_pc_software"
DB_USER = "systemir_pc_software"
DB_PASS = "LVvUsz3gvZQsn9sCpY6m"

print(f"Attempting to connect to MySQL database...")
print(f"Host: {DB_HOST}")
print(f"User: {DB_USER}")
print(f"Database: {DB_NAME}")

try:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10
    )
    print("\n✅ SUCCESS! Connection established.")
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT VERSION()")
        result = cursor.fetchone()
        print(f"Database Version: {result}")
        
    connection.close()
    
except pymysql.err.OperationalError as e:
    print(f"\n❌ CONNECTION FAILED: {e}")
    print("\nPossible causes:")
    print("1. 'Remote MySQL' is not enabled in DirectAdmin (Most likely).")
    print("   -> Go to DirectAdmin > Remote MySQL > Add '%' in the Access Host field.")
    print("2. The Host address is incorrect.")
    print("3. Firewall is blocking port 3306.")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
