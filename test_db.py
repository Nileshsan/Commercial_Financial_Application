import mysql.connector

try:
    connection = mysql.connector.connect(
        host="217.21.91.52",
        user="u782070381_PBS_Solutions",
        password="pbscfaAI25",
        database="u782070381_CFA_project_DB"
    )
    
    if connection.is_connected():
        print("Successfully connected to the database!")
        cursor = connection.cursor()
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"MySQL version: {version[0]}")
        
except mysql.connector.Error as e:
    print(f"Error connecting to MySQL: {e}")
finally:
    if 'connection' in locals() and connection.is_connected():
        cursor.close()
        connection.close()
        print("MySQL connection is closed")
