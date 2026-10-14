
import psycopg2

try:
    connection = psycopg2.connect(
        host="localhost",
        port=5432,
        database="pulseiq_db",
        user="postgres",
        password=input("Enter PostgreSQL password: ")
    )

    print("PostgreSQL connection successful!")

    connection.close()

except Exception as error:
    print("Connection failed:", error)
