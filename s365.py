# -*- coding: utf-8 -*-
"""
Cliente de la API no oficial de 365Scores, con reintentos y caché en disco.
Todas las funciones devuelven datos ya "limpios" (diccionarios simples).
"""
import hashlib
import json
import os
import time
from datetime import datetime

import re
from urllib.parse import parse_qsl, urlsplit

import requests

import config

_session = requests.Session()
_session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
    "Referer": "https://www.365scores.com/",
})

# Tiempos de vida de la caché (segundos)
MIN = 60
HORA = 3600
DIA = 86400


# ------------------------------------------------------------------
# Caché y llamadas
# ------------------------------------------------------------------
def _ruta_cache(path, params):
    clave = path + "?" + json.dumps(params, sort_keys=True)
    h = hashlib.md5(clave.encode("utf-8")).hexdigest()
    return os.path.join(config.CARPETA_CACHE, h + ".json")


def limpiar_cache():
    """Borra archivos de caché muy viejos para que la carpeta no crezca sin fin."""
    if not os.path.isdir(config.CARPETA_CACHE):
        return
    limite = time.time() - config.DIAS_BORRAR_CACHE * DIA
    for f in os.listdir(config.CARPETA_CACHE):
        ruta = os.path.join(config.CARPETA_CACHE, f)
        try:
            if os.path.getmtime(ruta) < limite:
                os.remove(ruta)
        except OSError:
            pass


def _get(path, params=None, ttl=10 * MIN):
    params = dict(params or {})
    todos = dict(config.API_PARAMS)
    todos.update(params)
    ruta = _ruta_cache(path, todos)

    # 1) ¿Está en caché y vigente?
    if ttl and os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                guardado = json.load(f)
            if time.time() - guardado["t"] < ttl:
                return guardado["data"]
        except (ValueError, KeyError, OSError):
            pass

    # 2) Llamar a la API con reintentos y espera creciente
    url = config.API_BASE + path
    ultimo_error = None
    for intento in range(config.REINTENTOS):
        try:
            time.sleep(config.PAUSA_ENTRE_LLAMADAS)
            r = _session.get(url, params=todos, timeout=20)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError("HTTP %s" % r.status_code)
            r.raise_for_status()
            data = r.json()
            os.makedirs(config.CARPETA_CACHE, exist_ok=True)
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"t": time.time(), "data": data}, f)
            return data
        except Exception as e:  # noqa: BLE001
            ultimo_error = e
            espera = 2 ** (intento + 1)
            print("  ! %s falló (%s). Reintento en %ss" % (path, e, espera))
            time.sleep(espera)

    # 3) Si todo falla, usar la caché vieja aunque esté vencida
    if os.path.exists(ruta):
        try:
            with open(ruta, encoding="utf-8") as f:
                print("  ! usando caché vencida para", path)
                return json.load(f)["data"]
        except (ValueError, KeyError, OSError):
            pass
    print("  ! sin datos para %s: %s" % (path, ultimo_error))
    return None


# ------------------------------------------------------------------
# Normalización de un partido
# ------------------------------------------------------------------
def _num(x, defecto=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return defecto


def _nombre(comp):
    return comp.get("shortName") or comp.get("name") or "?"


def normalizar(g):
    """Convierte un 'game' de 365Scores en un dict simple."""
    h = g.get("homeCompetitor") or {}
    a = g.get("awayCompetitor") or {}
    hg = _num(h.get("score"), -1)
    ag = _num(a.get("score"), -1)
    inicio = None
    try:
        inicio = datetime.fromisoformat(g.get("startTime"))
    except (TypeError, ValueError):
        pass
    return {
        "id": g.get("id"),
        "comp_id": g.get("competitionId"),
        "comp_nombre": g.get("competitionDisplayName") or "",
        "inicio": inicio,
        "estado": g.get("statusGroup"),       # 2 programado, 3 en vivo, 4 terminado
        "estado_txt": g.get("statusText") or "",
        "local_id": h.get("id"),
        "local": _nombre(h),
        "visita_id": a.get("id"),
        "visita": _nombre(a),
        "gl": int(hg) if hg is not None and hg >= 0 else None,
        "gv": int(ag) if ag is not None and ag >= 0 else None,
    }


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------
def partidos_por_fecha(fecha, competiciones):
    """fecha: date. Devuelve lista de partidos normalizados de esas competiciones."""
    txt = fecha.strftime("%d/%m/%Y")
    data = _get("/games/allscores/", {
        "competitions": ",".join(str(c) for c in competiciones),
        "startDate": txt, "endDate": txt,
    }, ttl=20 * MIN)
    if not data:
        return []
    out = []
    for g in data.get("games", []):
        p = normalizar(g)
        if p["comp_id"] in competiciones and p["inicio"] and p["inicio"].date() == fecha:
            out.append(p)
    return out


def _pagina(ruta_relativa, ttl):
    """Sigue un enlace de paginación tipo '/web/games/?a=1&b=2'."""
    partes = urlsplit(ruta_relativa)
    path = partes.path
    if path.startswith("/web"):
        path = path[4:]
    params = dict(parse_qsl(partes.query))
    return _get(path, params, ttl=ttl)


def resultados(equipo_id, paginas_extra=None):
    """Últimos partidos jugados de un equipo (todas las competiciones),
    siguiendo la paginación hacia atrás para tener más historial."""
    if paginas_extra is None:
        paginas_extra = config.PAGINAS_HISTORIAL_EXTRA
    data = _get("/games/results/", {"competitors": equipo_id}, ttl=3 * HORA)
    if not data:
        return []
    juegos = list(data.get("games", []))
    anterior = (data.get("paging") or {}).get("previousPage")
    for _ in range(paginas_extra):
        if not anterior:
            break
        pag = _pagina(anterior, ttl=2 * DIA)   # partidos viejos: casi no cambian
        if not pag:
            break
        juegos += pag.get("games", [])
        anterior = (pag.get("paging") or {}).get("previousPage")
    return [normalizar(g) for g in juegos]


def h2h(game_id):
    """Devuelve (lista H2H, recientes_local, recientes_visita) normalizados."""
    data = _get("/games/h2h/", {"gameId": game_id}, ttl=6 * HORA)
    if not data or "game" not in data:
        return [], [], []
    g = data["game"]
    lista = [normalizar(x) for x in g.get("h2hGames", [])]
    rl = [normalizar(x) for x in (g.get("homeCompetitor") or {}).get("recentGames", [])]
    rv = [normalizar(x) for x in (g.get("awayCompetitor") or {}).get("recentGames", [])]
    return lista, rl, rv


def detalle(game_id, terminado=False):
    """Detalle del partido. Si ya terminó, se guarda en caché por mucho tiempo."""
    data = _get("/game/", {"gameId": game_id}, ttl=30 * DIA if terminado else 10 * MIN)
    if not data or "game" not in data:
        return None
    return data["game"]


def marcador_90(game):
    """(goles local, goles visita) al final de los 90' (sin prórroga ni penales)."""
    if not game:
        return None
    for st in game.get("stages") or []:
        if st.get("id") == 9:   # "Fin de los 90 minutos"
            a, b = _num(st.get("homeCompetitorScore")), _num(st.get("awayCompetitorScore"))
            if a is not None and b is not None and a >= 0 and b >= 0:
                return int(a), int(b)
    h = _num((game.get("homeCompetitor") or {}).get("score"), -1)
    a = _num((game.get("awayCompetitor") or {}).get("score"), -1)
    if h >= 0 and a >= 0:
        return int(h), int(a)
    return None


def marcador_descanso(game):
    """(goles local, goles visita) al descanso, o None si no está."""
    if not game:
        return None
    for st in game.get("stages") or []:
        if st.get("id") == 7:   # "Descanso"
            a, b = _num(st.get("homeCompetitorScore")), _num(st.get("awayCompetitorScore"))
            if a is not None and b is not None and a >= 0 and b >= 0:
                return int(a), int(b)
    return None


def estadisticas(game_id):
    """Stats del partido completo:
    {competitor_id: {'corners','amarillas','rojas','xg','remates_puerta','grandes_chances'}}."""
    data = _get("/game/stats/", {"games": game_id}, ttl=30 * DIA)
    if not data:
        return None
    out = {}
    ids = {8: "corners", 1: "amarillas", 2: "rojas", 76: "xg", 4: "remates_puerta", 24: "grandes_chances"}
    for s in data.get("statistics", []):
        cid = s.get("competitorId")
        clave = ids.get(s.get("id"))
        if cid is None or clave is None:
            continue
        v = _num(str(s.get("value", "")).split("/")[0].replace("%", "").strip())
        if v is None:
            continue
        out.setdefault(cid, {})[clave] = v
    return out or None


def tabla(comp_id):
    """Filas de la tabla: lista de dicts {id, nombre, pos, pts, pj, zona}."""
    data = _get("/standings/", {"competitions": comp_id}, ttl=6 * HORA)
    if not data or not data.get("standings"):
        return []
    filas = []
    for st in data["standings"]:
        for r in st.get("rows", []):
            c = r.get("competitor") or {}
            filas.append({
                "id": c.get("id"),
                "nombre": _nombre(c),
                "pos": r.get("position"),
                "pts": _num(r.get("points"), 0),
                "pj": r.get("gamePlayed"),
                "zona": r.get("destinationNum"),
                "grupo": st.get("groupNum") or st.get("displayName"),
            })
        break  # solo la fase/tabla actual
    return filas


def _numero_en(texto, palabra):
    m = re.search(palabra + r"\D*\((\d+)", texto or "", re.IGNORECASE)
    return int(m.group(1)) if m else 0


def bajas(game_id):
    """Jugadores que NO estarán (lesionados/suspendidos) según 365Scores.
    Devuelve {'local': [...], 'visita': [...], 'confirmadas': bool}.
    Cada jugador: {'nombre','motivo','goles','asist'}."""
    g = detalle(game_id, terminado=False)
    if not g:
        return None
    nombres = {m.get("id"): (m.get("shortName") or m.get("name")) for m in g.get("members") or []}
    out = {"local": [], "visita": [], "confirmadas": False}
    for lado, clave in (("local", "homeCompetitor"), ("visita", "awayCompetitor")):
        lu = (g.get(clave) or {}).get("lineups") or {}
        if (lu.get("status") or "").lower().startswith("confirm"):
            out["confirmadas"] = True
        for m in lu.get("members") or []:
            if m.get("status") != 3:
                continue
            info = m.get("injury") or m.get("suspension") or {}
            motivo = info.get("reason") or m.get("statusText") or "baja"
            textos = " ".join(s.get("text", "") for s in m.get("seasonStats") or [])
            out[lado].append({
                "nombre": nombres.get(m.get("id"), "?"),
                "motivo": motivo,
                "goles": _numero_en(textos, "Goleador"),
                "asist": _numero_en(textos, "Asistencias"),
            })
        out[lado].sort(key=lambda j: (-j["goles"], -j["asist"]))
    return out


def cuotas(game_id):
    """Líneas de Bet365 del partido (lista cruda de 'lines')."""
    data = _get("/bets/lines/", {"games": game_id}, ttl=30 * MIN)
    if not data:
        return []
    return [ln for ln in data.get("lines", []) if ln.get("bookmakerId") == config.BOOKMAKER_ID]
