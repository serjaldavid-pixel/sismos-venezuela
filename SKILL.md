---
name: sismos-venezuela-monitor
description: >
  Levanta un servidor local que monitorea en vivo la actividad sísmica de Venezuela
  combinando tres fuentes (USGS + EMSC + FUNVISIS) en un mapa interactivo. Usar SIEMPRE
  que David quiera ver sismos/temblores/terremotos de Venezuela en tiempo real, abrir el
  monitor sísmico, levantar el mapa de sismos, o pida "arrancá el monitor de sismos",
  "mostrame los temblores en Venezuela", "abrí el mapa sísmico", o cualquier variante.
  El servidor corre 100% local: el navegador habla con localhost (no con las APIs externas),
  por lo que NO hay problemas de CORS y todas las fuentes cargan completas, incluyendo los
  microsismos de baja magnitud que FUNVISIS registra y que USGS por sí solo no muestra.
---

# Monitor Sísmico de Venezuela

Servidor web local que combina y muestra en vivo todos los sismos de Venezuela desde tres
fuentes oficiales/internacionales, en un mapa interactivo que se actualiza solo cada 5 minutos.

## Por qué un servidor local (y no un HTML suelto)

Un archivo HTML abierto directo en el navegador NO puede leer EMSC ni FUNVISIS por la regla
de seguridad CORS: el navegador bloquea silenciosamente esas respuestas y solo queda USGS,
que muestra muy pocos eventos. Este skill resuelve eso poniendo un servidor Python en el
medio: el navegador pide los datos a `localhost`, y es el servidor (sin restricciones CORS)
quien sale a buscar las tres fuentes y las combina. Resultado: cobertura completa, sin
depender de proxies públicos frágiles.

## Fuentes integradas

- **FUNVISIS** (`sismosve.rafnixg.dev`): autoridad nacional venezolana. Única con TODAS las
  magnitudes, incluyendo réplicas pequeñas (M1-M2).
- **USGS** (`earthquake.usgs.gov`): referencia internacional de EE.UU.
- **EMSC** (`seismicportal.eu`): catálogo europeo, alta densidad de eventos.

Cobertura geográfica: bounding box de Venezuela (lat 0.4–13.0, lon -73.8 a -59.4).

## Cómo se usa

### Opción rápida (Windows): doble clic
Hacer doble clic en **`arrancar.bat`**. Instala dependencias si hace falta, levanta el
servidor y abre el navegador solo.

### Opción manual
```
pip install -r requirements.txt
python scripts/server.py
```
Luego abrir `http://localhost:8000`. Para detener: cerrar la ventana o Ctrl+C.

### Parámetros opcionales
```
python scripts/server.py --port 8080          # otro puerto
python scripts/server.py --start 2026-06-23    # cambiar fecha de inicio
python scripts/server.py --no-browser          # no abrir el navegador solo
```

## Qué muestra el mapa

- Cada sismo es un círculo: color por magnitud (verde <3, amarillo 3-4, naranja 4-5, rojo 5+),
  tamaño proporcional a la magnitud, y borde distinto por fuente.
- Panel lateral con lista ordenada por fecha (clic = vuela al punto en el mapa).
- Filtro de magnitud mínima, contador de eventos por fuente, mini-sismograma, y botón de
  actualización manual además del refresco automático cada 5 minutos.
- Checkboxes para prender/apagar cada fuente.

## Archivos

- `scripts/server.py` — servidor Flask + fetchers/parsers de las 3 fuentes + caché en memoria.
- `scripts/index.html` — frontend del mapa (Leaflet) que consume el endpoint local `/api/sismos`.
- `arrancar.bat` — lanzador de doble clic para Windows.
- `requirements.txt` — dependencias (flask, requests).

## Notas

- Ninguna fuente del mundo garantiza el 100% absoluto de microsismos en tiempo real; depende
  de cuántas estaciones detectan cada evento y del retraso de procesamiento. Estas 3 fuentes
  combinadas dan la cobertura más completa posible desde APIs públicas.
- Para datos críticos de emergencia, la autoridad final sigue siendo FUNVISIS directo:
  http://www.funvisis.gob.ve/monitor.html
