# enbici — Next Steps


## ⚠️ Reglas UI (Evitar Regresiones de Caché y Estado)
- **Persistencia en `st.session_state`:** Almacenar siempre los resultados (métricas, coordenadas, perfiles) en `st.session_state` antes de dibujar la UI.
- **Renderizado fuera del botón:** Renderizar mapas, gráficos y botones de descarga fuera del bloque `if st.button("Calcular Ruta"):` leyendo desde `session_state` para evitar que se reseteen al interactuar.
- **Claves Dinámicas:** Asignar un `key` dinámico basado en la ruta/parámetros a componentes interactivos (Plotly, Folium) para forzar re-renderizado en búsquedas consecutivas.

---

## Roadmap de Mejoras

### 1. Campo de Viento Multipunto (Grid Barrial)
- **Objetivo:** Capturar la variación del viento entre zonas costeras (Rambla/Pocitos) e interiores (Prado/Colón).
- **Cambios:**
  - `src/api/weather.py`: Consultar Open-Meteo enviando una lista de coordenadas clave (4-6 nodos/barrios en Montevideo) en una única llamada HTTP.
  - `src/routing/cost.py`: Asignar a cada arista el vector de viento del punto del grid más cercano para un cálculo de `headwind` micro-local.

### 2. Exportación a Formato GPX
- **Objetivo:** Bajar la ruta para navegarla en Strava, Garmin u OsmAnd.
- **Cambios:**
  - Crear generador XML/GPX desde las coordenadas del trayecto.
  - Sumar `st.download_button` en `app_streamlit.py` leyendo el contenido GPX desde `st.session_state`.