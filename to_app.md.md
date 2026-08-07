# **enbici — Plan de Transición a App Móvil (to\_app.md)**

**Estado del Backend:** FastAPI REST API (Totalmente funcional y validado)  
**Objetivo:** Cliente móvil nativo/híbrido (iOS/Android) enfocado en navegación urbana minimalista (UX Map-First) consumiendo la API REST existente.

## ---

**1\. Visión y Enfoque del MVP Móvil**

Convertir el motor de ruteo de **enbici** en una aplicación móvil ligera y funcional (*client-side only*) optimizada para uso en bicicleta (*on-the-go*).

> * **Filosofía de Diseño:** Navegación estándar tipo Google Maps / Apple Maps / Citymapper.  
> * **Minimalismo Funcional:** Exponer únicamente los datos soportados por el backend actual sin recargar la interfaz ni agregar métricas inventadas.  
> * **Consumo Eficiente de API:** El teléfono no procesa el grafo ni algoritmos pesados (Dijkstra); se limita a realizar solicitudes HTTP y renderizar la geometría y métricas recibidas.  
> * **Evolución Futura (A tener en cuenta, NO implementar ahora):** La arquitectura debe quedar preparada para la recolección de datos anónimos de uso y métricas de rutas en futuras versiones.

## ---

**2\. Especificación de la API Backend Existente**

### **Endpoint Principal: GET /route**

El backend actual en FastAPI gestiona la carga del grafo en memoria una única vez (lifespan) y expone la lógica de ruteo.

#### **Parámetros de Consulta (Query Params):**

| Parámetro | Tipo | Default | Descripción   |
| :---- | :---- | :---- | :---- |
| origin\_place | string | null | Nombre del lugar de origen (ej. "Plaza Independencia") |
| dest\_place | string | null | Nombre del lugar de destino (ej. "Cerro de Montevideo") |
| origin\_lat / origin\_lon | float | null | Coordenadas explícitas de origen (fallback si no se usa texto) |
| dest\_lat / dest\_lon | float | null | Coordenadas explícitas de destino (fallback si no se usa texto) |
| elevation\_weight | float | 5.0 | Factor de penalización por repechos (0.0 a 10.0, no lineal \>3%) |
| wind\_weight | float | 0.0 | Factor de ponderación de viento en tiempo real (0.0 a 10.0) |
| allow\_parks | boolean | true | Permite o penaliza (10x) el paso por senderos de parques/plazas |

#### **Estructura de Respuesta JSON (200 OK):**

`{`  
  `"distance_km": 11.59,`  
  `"elevation_gain_m": 195.0,`  
  `"node_count": 81,`  
  `"map_url": "/static/ruta_montevideo.html",`  
  `"wind_metrics": {`  
    `"wind_speed_ms": 7.5,`  
    `"wind_direction_deg": 45.0,`  
    `"average_headwind_factor": 0.65`  
  `}`  
`}`

## ---

**3\. Guía de Diseño UI / UX Móvil (Navegación Estándar)**

### **Layout General (Pantalla Única / Map-First)**

> 1. **Mapa a Pantalla Completa (Full-bleed Map):** El mapa interactivo ocupa el 100% del fondo de la pantalla.  
> 2. **Barra de Búsqueda Flotante Superior (Top Bar):**  
   * Card flotante con bordes redondeados y sombra sutil.  
   * Input de Origen (con opción por defecto *"Mi ubicación actual"* mediante GPS nativo).  
   * Input de Destino.  
   * Botón desplegable/modal para ajustar sliders de preferencia (Elevación, Viento, Checkbox de Parques).  
> 3. **Ficha Resumen Inferior (Bottom Sheet Deslizable):**  
   * Despliega el resumen del viaje al calcular la ruta:  
     * **Distancia total:** km.  
     * **Tiempo estimado:** calculado a 15 km/h.  
     * **Desnivel positivo:** m subidos.  
     * **Viento:** velocidad (m/s) e indicador de viento de frente si \`wind\_weight \> 0\`.  
   * **Perfil de Elevación:** Gráfico de área simplificado (altitud vs distancia) en la parte expandida del Bottom Sheet.  
   * **Botón CTA Principal:** "Iniciar / Comenzar" en color de alto contraste.

## ---

**4\. Consideraciones Técnicas Móviles**

> * **Geolocalización:** Permisos de ubicación nativos (GPS) para establecer el origen sin necesidad de escribir.  
> * **Renderizado de Mapa:** Uso de SDK nativo de mapas (MapBox SDK / Google Maps SDK / MapKit) para dibujar la Polyline de la ruta y los marcadores de Origen/Destino parseados de la respuesta.  
> * **Manejo de Errores:** Mensajes limpios ante fallos de conexión, lugar no encontrado (400) o sin ruta posible (404).

## ---

**5\. Checklist para Agentes de Código / Desarrolladores**

> 1. Configurar el proyecto móvil (Flutter / React Native / Swift / Kotlin).  
> 2. Crear el cliente HTTP para conectar con la API FastAPI en /route y /health.  
> 3. Implementar la UI Map-First con Top Bar flotante y Bottom Sheet.  
> 4. Renderizar la polyline y marcadores en el mapa nativo.  
> 5. Validar el flujo completo: *GPS Origen → Búsqueda Destino → Consulta REST → Visualización en Mapa/Bottom Sheet*.