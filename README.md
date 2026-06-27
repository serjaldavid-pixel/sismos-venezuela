# Monitor Sísmico de Venezuela

Servidor local que muestra en vivo todos los sismos de Venezuela combinando
**USGS + EMSC + FUNVISIS** en un mapa interactivo.

## Instalación

1. Descomprimí esta carpeta donde tengas tus otros skills, por ejemplo:
   `C:\Users\ACER NITRO\Desktop\Claude Skills\sismos-venezuela-monitor\`

2. Asegurate de tener Python instalado (ya lo tenés por tus otros skills).

## Uso

**Forma fácil:** doble clic en `arrancar.bat`. Se abre el navegador solo.

**Forma manual:**
```
pip install -r requirements.txt
python scripts/server.py
```
Después abrí `http://localhost:8000` en el navegador.

Para detenerlo: cerrá la ventana negra (o Ctrl+C).

## ¿Por qué esto carga más sismos que el HTML suelto?

Porque el servidor (no el navegador) es quien busca los datos, esquivando el
bloqueo CORS que impedía leer EMSC y FUNVISIS desde un archivo HTML normal.
Ahora las tres fuentes cargan completas, incluyendo los microsismos M1-M2 que
solo registra FUNVISIS.

## Estructura

```
sismos-venezuela-monitor/
├── SKILL.md
├── README.md
├── requirements.txt
├── arrancar.bat            <- doble clic para arrancar
└── scripts/
    ├── server.py           <- servidor + combina las 3 fuentes
    └── index.html          <- el mapa
```
