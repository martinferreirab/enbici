import sqlite3
import pandas as pd

# Conectar a la base de datos de SQLite
conn = sqlite3.connect("data/enbici.db")

# Consulta usando los nombres exactos en plural
query = """
    SELECT j.*, u.username 
    FROM journey_logs j
    JOIN users u ON j.user_id = u.id
"""

df = pd.read_sql_query(query, conn)
conn.close()

# Mostrar en consola
print("--- HISTORIAL DE VIAJES (TELEMETRÍA) ---")
print(df)

# Guardar los datos en un archivo CSV en el directorio local
df.to_csv("data/historial_viajes.csv", index=False)
print("\n Archivo CSV guardado exitosamente en: data/historial_viajes.csv")