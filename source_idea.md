# Proyecto enbici - Specification Document

## Contexto y Objetivo
En Montevideo, Uruguay, las aplicaciones de navegación convencionales no ofrecen ruteo optimizado para bicicletas ni consideran variables topográficas (pendientes/elevación) o climáticas (viento/lluvia).

El objetivo de enbici es desarrollar un motor de ruteo en Python sobre el grafo vial de OpenStreetMap (OSM) que permita calcular rutas óptimas ajustadas por ponderaciones de esfuerzo personalizables (elevación y clima).

---

## Requisitos Funcionales

1. Extracción e ingestión del mapa vial de Montevideo desde OpenStreetMap.
2. Incorporación de datos de elevación por nodo y cálculo de pendiente (grade %) por segmento de calle.
3. Definición de algoritmo de ruteo con función de costo personalizada:
   Costo = Distancia * (1 + peso_elevacion * max(0, Pendiente))
4. Generación de salida en formato JSON y renderizado de mapa interactivo en HTML con métricas del recorrido (distancia total, desnivel positivo acumulado).
5. Exposición de la funcionalidad mediante API REST con FastAPI.
6. Integración de la API de Open-Meteo para ajustar el peso del costo en función del vector de viento respecto a la orientación de la calle.

---

## Especificaciones Tecnológicas

- Lenguaje: Python 3.12+
- Gestor de dependencias: uv
- Procesamiento espacial y grafos: osmnx, networkx, geopy
- Visualización: folium
- Backend API: FastAPI, uvicorn
- Fuertes de datos externas: Open-Elevation / SRTM (elevación), Open-Meteo API (clima)

---

## Plan de Ejecución por Iteraciones

### Fase 1: MVP Motor de Grafos y Elevación
- Descargar y persistir localmente el grafo de Montevideo (.graphml) usando osmnx.
- Mapear altitud a los nodos y calcular pendientes de aristas.
- Implementar algoritmo de camino mínimo (Dijkstra / A*) con la función de costo ponderada.
- Crear script de validación que genere el reporte de ruta y el archivo HTML con folium.

### Fase 2: API REST
- Implementar endpoint GET /route en FastAPI.
- Parámetros de entrada: origin_lat, origin_lon, dest_lat, dest_lon, elevation_weight (0 a 10).
- Respuesta: GeoJSON de la ruta, resumen de distancia, desnivel acumulado y link/render del HTML.

### Fase 3: Ponderación Climática
- Consumir dirección y velocidad de viento en tiempo real desde Open-Meteo.
- Calcular ángulo de incidencia del viento sobre cada segmento del grafo.
- Extender la función de costo con el parámetro wind_weight.

### Fase 4: Interfaz de Validación
- Implementar UI liviana con Streamlit para ajuste interactivo de parámetros.

---

## Directivas de Código para el Agente
- Modularizar componentes: /src/graph, /src/routing, /src/api, /src/utils.
- Usar type hints explícitos y docstrings concisos.
- Implementar caché local para el archivo del grafo (.graphml) para evitar descargas redundantes.
- Ejecutar la gestión de entorno e instalación de paquetes exclusivamente mediante `uv`.