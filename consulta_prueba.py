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

# Puntos GPS de cada viaje, en orden cronológico
telemetry_query = """
    SELECT t.id, t.journey_id, u.username, j.origin_place, j.dest_place,
           t.timestamp, t.lat, t.lon, t.speed_ms
    FROM journey_telemetry t
    JOIN journey_logs j ON t.journey_id = j.id
    JOIN users u ON j.user_id = u.id
    ORDER BY t.journey_id, t.timestamp
"""

df = pd.read_sql_query(query, conn)
df_telemetry = pd.read_sql_query(telemetry_query, conn)
conn.close()

# Mostrar en consola
print("--- HISTORIAL DE VIAJES ---")
print(df)

print("\n--- TELEMETRÍA (UBICACIÓN DEL USUARIO EN EL TIEMPO) ---")
print(df_telemetry)

# Guardar los datos en archivos CSV en el directorio local
df.to_csv("data/historial_viajes.csv", index=False)
df_telemetry.to_csv("data/telemetria_viajes.csv", index=False)
print("\n Archivos CSV guardados en: data/historial_viajes.csv y data/telemetria_viajes.csv")
