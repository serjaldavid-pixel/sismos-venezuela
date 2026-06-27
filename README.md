# Monitor Sísmico de Venezuela

Servidor local que muestra en vivo todos los sismos de Venezuela combinando
**USGS + EMSC + FUNVISIS** en un mapa interactivo.

## Instalación

1. Descomprimí esta carpeta en cualquiero lugar, por ejemplo el escritorio
   

2. Asegurate de tener Python instalado

## Uso

**Forma fácil:** doble clic en `arrancar.bat`. Se abre el navegador solo.

**Forma manual:**
```
pip install -r requirements.txt
python scripts/server.py
```
Después abrí `http://localhost:8000` en el navegador.

Para detenerlo: cerrá la ventana negra (o Ctrl+C).


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
