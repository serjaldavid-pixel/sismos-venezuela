#!/usr/bin/env python3
"""
server.py — Monitor Sísmico de Venezuela (servidor local)
=========================================================
Levanta un servidor web local que combina datos sísmicos de VENEZUELA desde
tres fuentes (USGS + EMSC + FUNVISIS) y los sirve a un mapa interactivo en vivo.

Como el servidor (no el navegador) sale a buscar los datos, NO hay problemas
de CORS ni dependencia de proxies públicos: todas las fuentes cargan completas.

Uso:
    python server.py
    python server.py --port 8080
    python server.py --start 2026-06-23      # fecha de inicio (por defecto: 2026-06-23)

Luego abrí en el navegador:  http://localhost:8000

Dependencias:
    pip install flask requests
"""

import argparse
import datetime as dt
import json
import os
import sys
import threading
import time
import webbrowser

try:
    import requests
    from flask import Flask, jsonify, send_from_directory, request as flask_request
except ImportError:
    print("Faltan dependencias. Instalá con:  pip install flask requests")
    sys.exit(1)

# --------------------------------------------------------------------------
# Configuración
# --------------------------------------------------------------------------
# Bounding box de Venezuela (+ margen costero/fronterizo razonable)
BBOX = {"minlat": 0.4, "maxlat": 13.0, "minlon": -73.8, "maxlon": -59.4}

FUNVISIS_URLS = [
    "https://sismosve.rafnixg.dev/api/sismos",
    "https://sismosve.rafnixg.dev/api/sismos/recent?limit=1000",
]

# Caché en memoria: se refresca en segundo plano cada REFRESH_SECONDS
CACHE = {"events": [], "updated": None, "errors": [], "counts": {}}
REFRESH_SECONDS = 300  # 5 minutos
START_DATE = "2026-06-23"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-VE,es;q=0.9,en;q=0.8",
    "Referer": "https://sismosve.rafnixg.dev/",
    "Origin": "https://sismosve.rafnixg.dev",
}
TIMEOUT = 25


# --------------------------------------------------------------------------
# Fetchers por fuente (cada uno devuelve lista de eventos normalizados)
# Formato normalizado: dict(mag, place, time_ms, lat, lon, depth, url, source)
# --------------------------------------------------------------------------
def _iso_end():
    end = dt.datetime.utcnow() + dt.timedelta(hours=6)  # margen de huso horario
    return end.strftime("%Y-%m-%dT%H:%M:%S")


def fetch_usgs():
    url = (
        "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
        f"&starttime={START_DATE}&endtime={_iso_end()}"
        f"&minlatitude={BBOX['minlat']}&maxlatitude={BBOX['maxlat']}"
        f"&minlongitude={BBOX['minlon']}&maxlongitude={BBOX['maxlon']}"
        "&orderby=time&limit=20000"
    )
    r = requests.get(url, headers=HTTP_HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates", [None, None, 0])
        out.append({
            "mag": p.get("mag") if p.get("mag") is not None else 0,
            "place": p.get("place") or "Venezuela",
            "time_ms": p.get("time"),
            "lat": c[1], "lon": c[0], "depth": c[2] or 0,
            "url": p.get("url"),
            "source": "usgs",
        })
    return out


def fetch_emsc():
    url = (
        "https://www.seismicportal.eu/fdsnws/event/1/query?format=json"
        f"&starttime={START_DATE}&endtime={_iso_end()}"
        f"&minlatitude={BBOX['minlat']}&maxlatitude={BBOX['maxlat']}"
        f"&minlongitude={BBOX['minlon']}&maxlongitude={BBOX['maxlon']}"
        "&limit=20000"
    )
    r = requests.get(url, headers=HTTP_HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for f in r.json().get("features", []):
        p = f.get("properties", {})
        geom = f.get("geometry", {})
        c = geom.get("coordinates", [p.get("lon"), p.get("lat"), p.get("depth")])
        t = p.get("time")
        time_ms = None
        if t:
            try:
                time_ms = int(dt.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp() * 1000)
            except Exception:
                time_ms = None
        out.append({
            "mag": p.get("mag") or 0,
            "place": p.get("flynn_region") or p.get("region") or "Venezuela",
            "time_ms": time_ms,
            "lat": c[1], "lon": c[0], "depth": p.get("depth") or (c[2] if len(c) > 2 else 0),
            "url": "https://www.seismicportal.eu/eventdetails.html?unid=" + str(p.get("unid", "")),
            "source": "emsc",
        })
    return out


def _parse_funvisis_payload(payload):
    out = []
    for f in payload.get("features", []):
        p = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates", [None, None])
        # date "dd-mm-yyyy", time "HH:MM" en hora local de Venezuela (UTC-4)
        time_ms = None
        try:
            d, m, y = (p.get("date") or "").split("-")
            hh = p.get("time") or "00:00"
            iso = f"{y}-{m}-{d}T{hh}:00-04:00"
            time_ms = int(dt.datetime.fromisoformat(iso).timestamp() * 1000)
        except Exception:
            pass
        depth = 0
        try:
            depth = float(str(p.get("depth", "0")).replace("km", "").strip())
        except Exception:
            pass
        out.append({
            "mag": float(p.get("value") or 0),
            "place": p.get("addressFormatted") or "Venezuela",
            "time_ms": time_ms,
            "lat": c[1], "lon": c[0], "depth": depth,
            "url": "http://www.funvisis.gob.ve/monitor.html",
            "source": "funvisis",
        })
    return out


def fetch_funvisis():
    merged = []
    for u in FUNVISIS_URLS:
        try:
            r = requests.get(u, headers=HTTP_HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            merged.extend(_parse_funvisis_payload(r.json()))
        except Exception:
            continue
    # dedup interno por (time, lat~, lon~)
    seen, unique = set(), []
    for ev in merged:
        if ev["lat"] is None or ev["lon"] is None:
            continue
        key = (ev["time_ms"], round(ev["lat"], 2), round(ev["lon"], 2))
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    if not unique:
        raise RuntimeError("sin datos")
    return unique


def _parse_sgc_payload(payload):
    out = []
    for f in payload.get("features", []):
        p = f.get("properties", {})
        c = f.get("geometry", {}).get("coordinates", [None, None, 0])
        if c[0] is None or c[1] is None:
            continue
        time_ms = None
        utc = p.get("utcTime") or ""
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                time_ms = int(dt.datetime.strptime(utc, fmt).replace(tzinfo=dt.timezone.utc).timestamp() * 1000)
                break
            except ValueError:
                continue
        if time_ms is None:
            continue
        try:
            mag = float(p.get("mag")) if p.get("mag") is not None else 0
        except (TypeError, ValueError):
            mag = 0
        # OJO: coordinates del SGC vienen [lat, lon, depth] (NO [lon, lat] como USGS)
        lat, lon, depth = c[0], c[1], (c[2] if len(c) > 2 else 0)
        if not (BBOX["minlat"] <= lat <= BBOX["maxlat"] and BBOX["minlon"] <= lon <= BBOX["maxlon"]):
            continue
        out.append({
            "mag": mag,
            "place": p.get("place") or p.get("closerTowns") or "Venezuela/Colombia",
            "time_ms": time_ms,
            "lat": lat, "lon": lon, "depth": depth or 0,
            "url": "https://www.sgc.gov.co/sismos",
            "source": "sgc",
        })
    return out


def fetch_sgc():
    # Servicio Geológico Colombiano — feeds GeoJSON oficiales (los que usa su visor).
    # Combinamos dos archivos para máxima cobertura:
    #   - five_days_all : TODOS los sismos (incluye M<4) de los últimos 5 días
    #   - sixty_days_4  : sismos M4+ de los últimos 60 días (histórico de los grandes)
    # Se deduplican los eventos repetidos entre ambos.
    urls = [
        "https://archive.sgc.gov.co/feed/v1.0.1/summary/five_days_all.json",
        "https://archive.sgc.gov.co/feed/v1.0.1/summary/sixty_days_4.json",
    ]
    merged = []
    ok = False
    for u in urls:
        try:
            r = requests.get(u, headers=HTTP_HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            merged.extend(_parse_sgc_payload(r.json()))
            ok = True
        except Exception:
            continue
    if not ok:
        raise RuntimeError("sin datos")
    # dedup por (tiempo redondeado a minuto, lat~, lon~)
    seen, unique = set(), []
    for ev in merged:
        key = (round(ev["time_ms"] / 60000), round(ev["lat"], 2), round(ev["lon"], 2))
        if key not in seen:
            seen.add(key)
            unique.append(ev)
    return unique


SOURCES = {"usgs": fetch_usgs, "emsc": fetch_emsc, "funvisis": fetch_funvisis, "sgc": fetch_sgc}


# --------------------------------------------------------------------------
# Refresco de caché
# --------------------------------------------------------------------------
def refresh_cache():
    all_events, errors, counts = [], [], {}
    start_ms = int(dt.datetime.fromisoformat(START_DATE + "T00:00:00-04:00").timestamp() * 1000)
    for name, fn in SOURCES.items():
        try:
            evs = [e for e in fn() if e.get("time_ms") and e["time_ms"] >= start_ms
                   and e.get("lat") is not None and e.get("lon") is not None]
            counts[name] = len(evs)
            all_events.extend(evs)
        except Exception as e:
            errors.append(f"{name.upper()}: {e}")
            counts[name] = 0
    all_events.sort(key=lambda e: e["time_ms"], reverse=True)
    CACHE["events"] = all_events
    CACHE["counts"] = counts
    CACHE["errors"] = errors
    CACHE["updated"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(all_events)
    detail = ", ".join(f"{k}:{v}" for k, v in counts.items())
    print(f"[{CACHE['updated']}] {total} sismos ({detail})" +
          (f" | errores: {'; '.join(errors)}" if errors else ""))


def background_refresher():
    while True:
        try:
            refresh_cache()
        except Exception as e:
            print("Error refrescando:", e)
        time.sleep(REFRESH_SECONDS)


# --------------------------------------------------------------------------
# App Flask
# --------------------------------------------------------------------------
app = Flask(__name__)
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

# Cuando corre bajo gunicorn (en Render), este módulo se importa en vez de
# ejecutarse con __main__. Inicializamos la caché y el refresco en ese caso.
_initialized = False
def _ensure_started():
    global _initialized
    if _initialized:
        return
    _initialized = True
    global START_DATE
    START_DATE = os.environ.get("START_DATE", START_DATE)
    refresh_cache()
    threading.Thread(target=background_refresher, daemon=True).start()

if os.environ.get("PORT"):
    # Estamos en un hosting (Render). Arrancar el refresco al importar.
    _ensure_started()


@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/api/sismos")
def api_sismos():
    return jsonify({
        "events": CACHE["events"],
        "updated": CACHE["updated"],
        "errors": CACHE["errors"],
        "counts": CACHE["counts"],
        "start_date": START_DATE,
    })


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    refresh_cache()
    return jsonify({"ok": True, "updated": CACHE["updated"], "counts": CACHE["counts"]})


def main():
    global START_DATE
    parser = argparse.ArgumentParser(description="Monitor Sísmico de Venezuela")
    parser.add_argument("--port", type=int, default=None, help="Puerto (por defecto 8000 local)")
    parser.add_argument("--start", default=START_DATE, help="Fecha de inicio YYYY-MM-DD")
    parser.add_argument("--no-browser", action="store_true", help="No abrir el navegador automáticamente")
    args = parser.parse_args()
    START_DATE = args.start

    # En Render (y otros hostings) el puerto y el host vienen del entorno.
    # En tu máquina, si no hay variable PORT, usa 8000 y abre el navegador solo.
    env_port = os.environ.get("PORT")
    is_cloud = env_port is not None
    port = args.port or (int(env_port) if env_port else 8000)
    host = "0.0.0.0" if is_cloud else "127.0.0.1"

    print("=" * 58)
    print("  MONITOR SÍSMICO DE VENEZUELA")
    print("  Fuentes: USGS + EMSC + FUNVISIS")
    print(f"  Desde: {START_DATE}")
    if not is_cloud:
        print(f"  Abrí en el navegador:  http://localhost:{port}")
        print("  (Cerrá esta ventana para detener el servidor)")
    print("=" * 58)

    # primer fetch sincrónico para que la página cargue con datos
    refresh_cache()
    threading.Thread(target=background_refresher, daemon=True).start()

    # Solo abrir navegador automáticamente si estamos en local
    if not is_cloud and not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    main()
