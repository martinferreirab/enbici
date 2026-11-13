# enbici: guia para entender el proyecto

## 1. Que estamos construyendo

`enbici` es un motor de ruteo para bicicletas en Montevideo. Su tarea principal es responder una pregunta como:

> "Quiero ir desde Plaza Independencia hasta la Facultad de Ingenieria. Que recorrido conviene hacer en bicicleta?"

El proyecto usa el mapa vial de OpenStreetMap y busca una ruta teniendo en cuenta mas que la distancia. Puede considerar:

- la distancia de cada tramo;
- las subidas, mediante los datos de elevacion del terreno;
- el viento actual, si se activa esa opcion;
- caminos internos de parques y plazas;
- algunos tramos en sentido contrario, si se permite esa tolerancia.

El resultado es una sola ruta de menor costo segun los parametros elegidos. La aplicacion muestra las metricas y puede generar un mapa HTML interactivo.

## 2. La idea general, sin programar

El programa trabaja con un **grafo**. En este contexto:

- un **nodo** es un punto del mapa, normalmente una interseccion o un punto de una calle;
- una **arista** es un tramo que une dos nodos;
- cada arista tiene datos como longitud, sentido de circulacion, pendiente y si atraviesa un parque.

El proceso completo es:

1. Se carga el grafo de Montevideo desde los archivos guardados en `data/`.
2. El usuario indica origen y destino. Puede escribir nombres o proporcionar coordenadas.
3. Los nombres se convierten en latitud y longitud mediante Nominatim/OpenStreetMap.
4. Cada coordenada se asocia al nodo del grafo mas cercano.
5. Se calcula un costo para cada tramo. Una subida o un viento de frente pueden hacer que un tramo sea menos conveniente aunque sea corto.
6. NetworkX aplica el algoritmo de Dijkstra para encontrar la ruta de menor costo.
7. Se calculan distancia, desnivel y datos de viento.
8. Folium genera un mapa HTML con la ruta, el origen, el destino y un resumen.

Una forma simple de imaginarlo es que cada calle tiene un "precio". El algoritmo no busca necesariamente la calle mas corta: busca la combinacion de calles cuyo precio total sea menor.

## 3. Estructura de carpetas

### Archivos de la raiz

Los archivos que estan directamente dentro de `enbici-main__` son los puntos de entrada, la configuracion y la documentacion del proyecto.

| Archivo | Para que sirve |
|---|---|
| `app_streamlit.py` | Interfaz grafica en el navegador. Permite buscar lugares, ajustar parametros, calcular una ruta, ver el mapa y ver el perfil de elevacion. |
| `main.py` | Script de validacion. Ejecuta una comparacion entre una ruta que prioriza distancia y otra que penaliza las subidas. Guarda un mapa de ejemplo en `output/`. |
| `run_server.py` | Intenta iniciar el servidor FastAPI con Uvicorn. Actualmente contiene una ruta absoluta de Linux (`/home/...`), por lo que puede no funcionar directamente en Windows. |
| `enrich_elevation.py` | Script antiguo y general para consultar elevaciones de todos los nodos. El flujo mas elaborado y actual es `scripts/enrich_elevation_idw.py`. |
| `pyproject.toml` | Define el nombre del proyecto, la version, la version minima de Python y las dependencias. |
| `uv.lock` | Guarda las versiones concretas que resolvio `uv` para que el entorno sea reproducible. No se edita a mano. |
| `.python-version` | Indica la version de Python seleccionada para el proyecto. |
| `.gitignore` | Indica que archivos generados, como `__pycache__` y entornos virtuales, no deberian subirse al control de versiones. |
| `README.md` | Punto de entrada tradicional de la documentacion. Antes de esta guia estaba vacio; ahora enlaza a este documento. |

### `cache/`: resultados auxiliares reutilizables

La carpeta `cache/` guarda respuestas o resultados temporales que pueden reutilizarse para no repetir consultas externas. En la copia actual hay dos archivos JSON con nombres hash.

Estos archivos no son el grafo principal de calles. El grafo principal esta en `data/`. Tampoco conviene editar manualmente los JSON: su contenido depende de las consultas que hayan realizado los programas.

La diferencia practica es:

- **cache**: ahorro de consultas y calculos auxiliares;
- **data**: datos geograficos persistentes que el sistema necesita para funcionar;
- **output**: resultados que el usuario puede abrir o visualizar.

### `data/`: datos de entrada y datos persistidos

Esta carpeta contiene la informacion geografica pesada del proyecto:

| Archivo | Para que sirve |
|---|---|
| `montevideo.graphml` | Grafo vial de Montevideo en formato GraphML, un formato XML que puede ser leido por OSMnx y NetworkX. Incluye nodos, calles, longitudes, elevaciones y pendientes. |
| `montevideo_final.pkl` | Version binaria del grafo final, lista para cargar rapidamente con Python. Es una cache de arranque y no se debe abrir ni editar a mano. |
| `elevation_samples_cache.json` | Elevaciones reales obtenidas para nodos de muestra desde Open-Meteo. Permite retomar el enriquecimiento sin volver a pedir todos los datos. |

Cuando se carga el grafo, `src/graph/loader.py` primero intenta usar `montevideo_final.pkl`. Si no existe, usa `montevideo.graphml`, prepara el grafo y vuelve a generar el `.pkl`.

Importante: si se modifica `montevideo.graphml` ejecutando un script de elevacion, hay que borrar `data/montevideo_final.pkl` para que la proxima ejecucion no siga usando la version binaria vieja.

### `output/`: resultados visibles

Aqui se guardan mapas HTML generados por Folium:

- `ruta_montevideo.html`: mapa generado por `main.py` o por la API;
- `ruta_streamlit.html`: mapa exportado desde la interfaz Streamlit;
- `park_traversal_test.html`: resultado de una prueba o exploracion de recorridos por parques.

Estos archivos se pueden abrir directamente en un navegador. Son resultados, no el codigo del motor. La API los publica ademas bajo la ruta `/static`.

### `scripts/`: tareas puntuales y pruebas

La carpeta contiene programas que se ejecutan manualmente para preparar datos o verificar comportamientos:

- `enrich_elevation_idw.py`: selecciona nodos de muestra, consulta elevaciones reales a Open-Meteo y estima la elevacion del resto mediante IDW, una interpolacion basada en los vecinos mas cercanos. Luego recalcula las pendientes de las aristas.
- `test_elevation_routing.py`: comprueba la formula de costo y compara rutas con distintos valores de `elevation_weight`. Sirve para saber si la elevacion realmente influye y para detectar datos de pendiente ausentes o fuera de rango.

Los scripts no se ejecutan automaticamente cada vez que se abre la aplicacion. Son herramientas de mantenimiento o validacion.

### `src/`: codigo reutilizable de la aplicacion

`src` significa normalmente "source", es decir, codigo fuente. La idea de separar este codigo en modulos es evitar que toda la aplicacion este dentro de un unico archivo.

#### `src/graph/`: preparacion del mapa como grafo

- `loader.py` carga el grafo, decide si usa el `.pkl` o el `.graphml`, descarga OpenStreetMap solo cuando no hay datos locales, marca caminos de parques y agrega alternativas de sentido contrario.
- `elevation.py` agrega elevacion a los nodos y calcula `grade`, que representa la pendiente relativa de cada tramo. La pendiente se limita actualmente a un maximo de 45%.

#### `src/routing/`: calculo de rutas

- `cost.py` contiene la funcion que transforma cada tramo en un costo. Penaliza las subidas, el viento de frente, los caminos de parques cuando estan deshabilitados y los tramos contra el sentido de circulacion.
- `pathfinder.py` busca el nodo mas cercano a una coordenada, ejecuta Dijkstra y calcula las metricas finales de la ruta.

#### `src/api/`: servidor y datos de la API

- `app.py` define la aplicacion FastAPI, carga el grafo una sola vez al iniciar y expone `/route` y `/health`.
- `buses.py` consulta posiciones actuales de omnibus a la API de la IM, las asocia al tramo de calle mas cercano y cachea el resultado durante 60 segundos.
- `schemas.py` define la forma de las respuestas usando Pydantic. Por ejemplo, la respuesta de una ruta incluye distancia, desnivel, cantidad de nodos, datos de viento opcionales y URL del mapa.
- `weather.py` consulta Open-Meteo para obtener viento actual en cuatro zonas de Montevideo. Para cada tramo se usa el punto de viento mas cercano.

#### `src/utils/`: utilidades

- `geocoding.py` convierte un nombre como `Plaza Independencia` en coordenadas usando Nominatim. Es lo que permite buscar por nombre en lugar de escribir latitud y longitud.

#### `src/visualization/`: presentacion de resultados

- `map_export.py` transforma la lista de nodos de una ruta en coordenadas y genera un mapa HTML con Folium, marcadores y metricas.

Los archivos `__init__.py` indican a Python que esas carpetas forman parte de los paquetes importables del proyecto.

## 4. Las dos formas de usar el sistema

### Opcion A: interfaz Streamlit

Es la opcion mas amigable para probar el proyecto. La pantalla tiene un panel lateral donde se ingresan origen y destino, se convierten nombres en coordenadas y se ajustan los parametros. En el area principal se muestran el mapa, las metricas y el perfil de elevacion.

El flujo es:

1. Escribir el lugar de origen y pulsar la busqueda correspondiente.
2. Escribir el destino y pulsar su busqueda.
3. Elegir cuanto se quieren evitar las subidas y, opcionalmente, considerar viento.
4. Decidir si se habilitan parques y cuanta tolerancia se da a tramos contra el sentido.
5. Pulsar `Calcular Ruta`.

Streamlit vuelve a ejecutar el archivo cuando cambia un control. Por eso `app_streamlit.py` usa `st.session_state`: ahi conserva las coordenadas y el resultado para que el mapa no desaparezca en cada interaccion.

### Opcion B: API FastAPI

Una API es un programa que espera solicitudes HTTP y devuelve datos. El endpoint principal es:

```text
GET /route
```

Acepta lugares por nombre o coordenadas. Ejemplo conceptual:

```text
/route?origin_place=Plaza%20Independencia&dest_place=Facultad%20de%20Ingenieria&elevation_weight=5
```

Tambien ofrece:

- `GET /health`: indica si el servidor esta funcionando y si el grafo fue cargado;
- `GET /docs`: documentacion interactiva generada por FastAPI, normalmente disponible en `http://127.0.0.1:8000/docs`.

La respuesta de `/route` no devuelve toda la geometria de la ruta en JSON. Devuelve metricas y una URL como `/static/ruta_montevideo.html`, donde se puede abrir el mapa generado.

## 5. Que significan los parametros

### `elevation_weight`

Va de 0 a 10. Con 0, la elevacion no cambia el costo y el algoritmo prioriza principalmente la distancia. Cuanto mayor es el valor, mayor es la penalizacion por subir.

La formula toma solo la pendiente ascendente. Una bajada no agrega penalizacion de elevacion porque el modelo supone que bajar no exige el mismo esfuerzo que subir.

### `wind_weight`

Va de 0 a 10. En 0 no se consulta el viento. Si es mayor que 0, se consulta Open-Meteo y se penalizan los tramos orientados contra el viento.

### `allow_parks`

Si esta activo, los caminos internos de parques y plazas reciben un incentivo. Si esta desactivado, se vuelven muy poco convenientes. Esto depende de las etiquetas existentes en OpenStreetMap y no significa que todos los parques tengan un atajo util.

### `max_against_traffic_blocks`

Va de 0 a 3. Con 0 no se permiten los tramos agregados contra el sentido en calles de un solo sentido. Los valores mayores permiten una tolerancia limitada, pero esos tramos siguen teniendo un costo alto.

## 6. Como se calcula el costo

De forma simplificada, cada tramo empieza con su longitud en metros. Luego se le aplican multiplicadores:

```text
costo = longitud
        x penalizacion por elevacion
        x multiplicador de parques
        x multiplicador contra el sentido
        x penalizacion por viento
```

La penalizacion de elevacion crece linealmente con la pendiente positiva. El factor de sensibilidad actual es 1.5: `costo = longitud * (1 + elevation_weight * pendiente * 1.5)`. Por ejemplo, para un tramo de 100 m con pendiente de 5% y `elevation_weight=10`, el costo es 175 m-equivalentes y el cociente es 1.75. El recargo por subidas consecutivas se activa solo cuando el cociente es estrictamente mayor que 1.75; por lo tanto, ese ejemplo exacto no lo activa. Cada tramo desde el segundo consecutivo que supera el umbral recibe un recargo adicional del 10%. Un tramo que no supera el umbral reinicia la secuencia. En bajada, el costo se calcula independientemente por tramo: menos del 10% conserva el costo normal; desde 10% hasta 25% inclusive cuesta el 75% de su longitud; y por encima del 25% cuesta el 50%. Dijkstra considera el historial de subidas consecutivas y el costo individual de cada bajada para elegir la suma menor.

Esto explica por que una ruta elegida con elevacion puede ser un poco mas larga que la ruta de distancia minima: esta intercambiando algunos metros extra por menos esfuerzo de subida.

## 7. Como ejecutar el proyecto

El proyecto requiere Python 3.12 o superior y usa `uv` para instalar dependencias y ejecutar comandos. Desde la carpeta del proyecto:

```powershell
uv sync
```

Para ejecutar la validacion del motor:

```powershell
uv run python main.py
```

Esto compara dos rutas y genera `output/ruta_montevideo.html`.

Para ejecutar la interfaz grafica:

```powershell
uv run streamlit run app_streamlit.py
```

Streamlit mostrara una direccion local, normalmente `http://localhost:8501`.

El calculo de rutas consulta posiciones de omnibus en tiempo real directamente a la API de la IM. Usa el endpoint OAuth que autentica el script `probar_omnibus.py` y reutiliza el token en memoria. No hace falta ejecutar ese script ni leer `omnibus_actuales.json` para calcular una ruta. Antes de iniciar Streamlit o FastAPI, configura las credenciales OAuth como variables de entorno en esa misma ventana de PowerShell:

```powershell
$env:MONTEVIDEO_CLIENT_ID = "tu-client-id"
$env:MONTEVIDEO_CLIENT_SECRET = "tu-client-secret"
```

No guardes el secreto en el codigo ni lo compartas en chats. Si ya fue divulgado, regeneralo desde el portal de la IM. Si faltan credenciales o falla la consulta, la aplicacion informa el error y no calcula una ruta como si hubiera considerado el transito.

Para validar el ajuste y la seleccion de ruta sin consultar la API:

```powershell
uv run python scripts/test_bus_traffic.py
```

Para ejecutar la API en Windows, la forma mas segura con el estado actual del repositorio es:

```powershell
uv run uvicorn src.api.app:app --host 127.0.0.1 --port 8000
```

Luego se puede abrir `http://127.0.0.1:8000/docs`.

Para comprobar el efecto de la elevacion:

```powershell
uv run python scripts/test_elevation_routing.py
```

El script de enriquecimiento de elevacion requiere conexion a Internet y consulta Open-Meteo. No conviene ejecutarlo como prueba cotidiana porque modifica datos grandes del proyecto:

```powershell
uv run python scripts/enrich_elevation_idw.py
```

Despues de regenerar `montevideo.graphml`, borrar `data/montevideo_final.pkl` antes de iniciar nuevamente la aplicacion.

## 8. Servicios externos y datos de Internet

El proyecto no es completamente autonomo. Usa servicios externos en momentos concretos:

- OpenStreetMap/OSMnx: origen del grafo vial, principalmente cuando aun no existe el archivo local.
- Nominatim: busqueda de nombres de lugares.
- Open-Meteo Elevation: elevaciones reales durante el enriquecimiento.
- Open-Meteo Forecast: viento actual cuando `wind_weight` es mayor que cero.
- API de Transporte Publico de la IM: posiciones de omnibus; se descartan posiciones de mas de cinco minutos y se asocian al tramo vial mas cercano si esta a 30 metros o menos. Cada tramo cuesta igual con 0 omnibus, 15% mas con 1 o 2, y 30% mas con 3 o mas. Este multiplicador se aplica al final del costo del tramo. La respuesta se cachea durante 60 segundos.

El costo final de un tramo se puede pensar como el costo calculado por elevacion, viento, parques y sentido de circulacion, multiplicado al final por el factor de omnibus. Por ejemplo, si antes del factor de omnibus costaba 100, pasa a 115 con 1 o 2 buses cerca y a 130 con 3 o mas. En Streamlit se muestra cuántos omnibus recientes quedaron asociados a los tramos de la ruta elegida.

Si falla uno de estos servicios, la causa puede ser falta de Internet, limites de uso, un nombre dificil de encontrar o una respuesta inesperada del servicio. El grafo ya guardado permite seguir trabajando sin volver a descargar OpenStreetMap.

## 9. Estado actual y cosas a tener en cuenta

- El proyecto calcula una sola ruta optima; no ofrece varias alternativas.
- La fase de ciclovias especificas fue removida del codigo actual. El grafo sigue siendo el grafo ciclista de OpenStreetMap, pero no hay una capa propia de ciclovias implementada.
- La precision de la elevacion depende de las muestras y de la interpolacion IDW. Dos calles cercanas pueden terminar con elevaciones parecidas, por lo que aumentar `elevation_weight` no siempre cambia el camino visible.
- `run_server.py` conserva una ruta de proyecto de Linux y deberia adaptarse si se quiere usar como comando principal en Windows.
- El archivo `to_app.md.md` es una especificacion de una futura aplicacion movil en React Native/Expo. No hay una carpeta movil dentro de este repositorio actual; ese documento describe una posible siguiente etapa.
- `next_steps.md` conserva ideas futuras como exportacion GPX y mejoras del viento. No todo lo que aparece ahi esta implementado en la version actual.

## 10. Resumen en una frase por carpeta

| Carpeta | Idea clave |
|---|---|
| `cache/` | Resultados auxiliares para no repetir consultas o calculos. |
| `data/` | Grafo y datos geograficos persistentes que alimentan el sistema. |
| `output/` | Mapas y resultados generados para abrir o compartir. |
| `scripts/` | Herramientas manuales de preparacion y comprobacion. |
| `src/` | Codigo principal reutilizable: grafo, rutas, API, clima y mapas. |

La distincion mas importante es esta: `data` alimenta a la aplicacion, `src` contiene las reglas que procesan esos datos, y `output` muestra el resultado.