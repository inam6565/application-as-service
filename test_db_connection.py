import mysql.connector
from mysql.connector import Error

# Replace the following values with your MySQL server credentials
host = "localhost"    # IP address or hostname of your MySQL server
database = "mysql"    # Name of the database you want to connect to
user = "root"         # Your MySQL username (e.g., 'root' or 'inam')
password = "my_sql_db_password"  # The password for the user

connection = None  # Initialize connection variable to avoid NameError

try:
    # Establish the connection
    connection = mysql.connector.connect(
        host=host,
        database=database,
        user=user,
        password=password
    )

    if connection.is_connected():
        print("Successfully connected to the database")
        
        # Example of executing a simple query
        cursor = connection.cursor()
        cursor.execute("SHOW TABLES")
        
        # Fetch and display the results
        tables = cursor.fetchall()
        print("Tables in the database:")
        for table in tables:
            print(table)

except Error as e:
    print(f"Error: {e}")

finally:
    # Close the connection if it was established
    if connection and connection.is_connected():
        cursor.close()
        connection.close()
        print("Connection closed")