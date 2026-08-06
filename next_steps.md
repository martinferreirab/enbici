# enbici — Next Steps

> Próximas funcionalidades a implementar en el proyecto enbici.

---

## Roadmap de mejoras

### 1. Búsqueda por Nombre de Lugar (Geocoding) ✅ COMPLETADA
- ✅ Usar `geopy` con `Nominatim` para resolver nombres de sitios/barrios/direcciones en Montevideo a coordenadas `(lat, lon)`.
- ✅ Integrar campos `st.text_input` para origen y destino en `app_streamlit.py` como alternativa/complemento a las coordenadas manuales y presets.
- ✅ Módulo `src/utils/geocoding.py` con función `geocode_place()`
- ✅ Validado: "Plaza Independencia", "Cerro", "Pocitos", "Facultad de Ingeniería" geocodifican correctamente

### 2. Detección Completa e Integración de Ciclovías ✅ COMPLETADA
- ✅ Ajustar `src/graph/loader.py` para parsear múltiples tags de OSM (`cycleway`, `cycleway:left`, `cycleway:right`, `highway=cycleway`, `bicycle=designated`).
- ✅ Configurar `ox.settings.useful_tags_way` antes de cargar el grafo.
- ✅ Asignar atributo `is_dedicated_bikeway: bool` en aristas y persistir en `data/montevideo.graphml`.
- ✅ Agregar `bikeway_weight` (0-10) en `edge_cost()`, `bikeway_percentage` en `RouteMetrics`, y slider correspondiente en Streamlit UI + API REST.