import sqlite3
import pandas as pd

from src.routing.cost import bus_traffic_multiplier

# Conectar a la base de datos de SQLite
conn = sqlite3.connect("data/enbici.db")

# Columnas explícitas: evita exportar password_hash y la columna id duplicada del JOIN
query = """
    SELECT j.id, j.user_id, u.username, j.origin_place, j.dest_place,
           j.distance_km, j.elevation_gain_m,
           j.elevation_weight, j.wind_weight, j.bus_weight,
           j.allow_parks, j.max_against_traffic_blocks,
           j.timestamp, j.is_started, j.is_completed
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

# Penalización por ómnibus aplicada a cada tramo según el bus_weight guardado
# (bus_weight = 0 -> sin penalización; viajes anteriores a la integración de buses quedan en 0)
df["mult_bus_1_2"] = df["bus_weight"].apply(lambda w: bus_traffic_multiplier(1, w)).round(2)
df["mult_bus_3_mas"] = df["bus_weight"].apply(lambda w: bus_traffic_multiplier(3, w)).round(2)

# Mostrar en consola
print("--- HISTORIAL DE VIAJES ---")
print(df)

print("\n--- TELEMETRÍA (UBICACIÓN DEL USUARIO EN EL TIEMPO) ---")
print(df_telemetry)

# Guardar los datos en archivos CSV en el directorio local
df.to_csv("data/historial_viajes.csv", index=False)
df_telemetry.to_csv("data/telemetria_viajes.csv", index=False)
print("\n Archivos CSV guardados en: data/historial_viajes.csv y data/telemetria_viajes.csv")
