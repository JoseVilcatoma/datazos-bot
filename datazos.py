# -*- coding: utf-8 -*-
"""
Cálculo de DATAZOS, modelo Poisson y sugerencia prepartido.

Regla de oro: cada frase sale de datos descargados y dice su muestra.
Si no hay datos suficientes, no se dice nada.
"""
import html
import math
from datetime import datetime

import config
import s365

PUNTAJE_MINIMO = 4.0


# =====================================================================
# Utilidades
# =====================================================================
def es_valido(p):
    """Partido terminado, con marcador y que no sea amistoso."""
    if p["estado"] != 4 or p["gl"] is None or p["gv"] is None:
        return False
    if p["comp_id"] in config.COMPETICIONES_EXCLUIDAS:
        return False
    nombre = (p["comp_nombre"] or "").lower()
    return not any(w in nombre for w in config.PALABRAS_EXCLUIDAS)


def vista(p, eq):
    """El partido p visto desde el equipo eq."""
    local = p["local_id"] == eq
    gf, gc = (p["gl"], p["gv"]) if local else (p["gv"], p["gl"])
    res = "G" if gf > gc else ("E" if gf == gc else "P")
    return {"p": p, "local": local, "gf": gf, "gc": gc, "res": res,
            "rival": p["visita"] if local else p["local"]}


def racha(vs, cond):
    n = 0
    for v in vs:
        if cond(v):
            n += 1
        else:
            break
    return n


def pl(n, uno, varios):
    return uno if n == 1 else varios


def fecha_txt(d):
    return d.strftime("%d/%m/%Y") if d else "?"


def historial(equipo_id, extra, antes_de):
    """Últimos partidos válidos de un equipo, del más nuevo al más viejo."""
    vistos = {}
    for p in s365.resultados(equipo_id) + list(extra):
        if p["id"] and p["id"] not in vistos:
            vistos[p["id"]] = p
    lista = [p for p in vistos.values()
             if es_valido(p) and p["inicio"] and p["inicio"] < antes_de
             and equipo_id in (p["local_id"], p["visita_id"])]
    lista.sort(key=lambda x: x["inicio"], reverse=True)
    return lista


def _dz(tipo, emoji, texto, puntaje, lados=None, frase=None):
    return {"tipo": tipo, "emoji": emoji, "texto": texto, "puntaje": round(puntaje, 2),
            "lados": lados or {}, "frase": frase or texto}


def _ext(p):
    """Qué tan extremo es un porcentaje (0 = 50%, 1 = 0% o 100%)."""
    return abs(p - 0.5) * 2


# =====================================================================
# Datazos de rachas y tendencias de un equipo
# =====================================================================
def datazos_equipo(nombre, vs, es_local):
    lado = "local" if es_local else "visita"
    contra = "visita" if es_local else "local"
    out = []
    todos = vs[:20]

    # ---- Rachas en todas las competiciones ----
    gan = racha(todos, lambda v: v["res"] == "G")
    inv = racha(todos, lambda v: v["res"] != "P")
    sg = racha(todos, lambda v: v["res"] != "G")
    der = racha(todos, lambda v: v["res"] == "P")
    marca = racha(todos, lambda v: v["gf"] > 0)
    sin_marcar = racha(todos, lambda v: v["gf"] == 0)
    cero = racha(todos, lambda v: v["gc"] == 0)
    recibe = racha(todos, lambda v: v["gc"] > 0)

    if gan >= 4:
        out.append(_dz("racha_" + lado, "📈", f"{nombre} ganó sus últimos {gan} partidos",
                       gan * 1.4, {lado: 1}))
    if inv >= 6 and inv > gan + 1:
        out.append(_dz("racha_" + lado, "📈", f"{nombre} lleva {inv} partidos sin perder",
                       inv * 1.0, {lado: 1}))
    if der >= 4:
        out.append(_dz("racha_" + lado, "📉", f"{nombre} perdió sus últimos {der} partidos",
                       der * 1.3, {contra: 1}))
    elif sg >= 5:
        out.append(_dz("racha_" + lado, "📉", f"{nombre} lleva {sg} partidos sin ganar",
                       sg * 1.1, {contra: 1}))
    if marca >= 8:
        out.append(_dz("ataque_" + lado, "⚽", f"{nombre} marcó en sus últimos {marca} partidos",
                       marca * 0.7, {"goles": 1}))
    if sin_marcar >= 3:
        out.append(_dz("ataque_" + lado, "🥶", f"{nombre} no marca hace {sin_marcar} partidos",
                       sin_marcar * 1.5, {"pocos": 1, contra: 0.5}))
    if cero >= 4:
        out.append(_dz("defensa_" + lado, "🧤", f"{nombre} no recibe gol hace {cero} partidos",
                       cero * 1.2, {"pocos": 1, lado: 0.5}))
    if recibe >= 8:
        out.append(_dz("defensa_" + lado, "🥅", f"{nombre} recibió gol en sus últimos {recibe} partidos",
                       recibe * 0.6, {"goles": 1}))

    # ---- Rachas como local / como visita ----
    sede = [v for v in todos if v["local"] == es_local]
    tag = "de local" if es_local else "de visita"
    s_gan = racha(sede, lambda v: v["res"] == "G")
    s_inv = racha(sede, lambda v: v["res"] != "P")
    s_sg = racha(sede, lambda v: v["res"] != "G")
    s_marca = racha(sede, lambda v: v["gf"] > 0)
    s_recibe = racha(sede, lambda v: v["gc"] > 0)
    s_cero = racha(sede, lambda v: v["gc"] == 0)
    if s_gan >= 4:
        out.append(_dz("sede_" + lado, "🏟️", f"{nombre} ganó sus últimos {s_gan} partidos {tag}",
                       s_gan * 1.5, {lado: 1}))
    elif s_inv >= 6:
        out.append(_dz("sede_" + lado, "🏟️", f"{nombre} no pierde {tag} hace {s_inv} partidos",
                       s_inv * 1.1, {lado: 1}))
    if s_sg >= 4:
        out.append(_dz("sede_" + lado, "🏟️", f"{nombre} no gana {tag} hace {s_sg} partidos",
                       s_sg * 1.2, {contra: 1}))
    if s_marca >= 7:
        out.append(_dz("sede_gol_" + lado, "⚽", f"{nombre} marcó en sus últimos {s_marca} partidos {tag}",
                       s_marca * 0.8, {"goles": 1}))
    if s_recibe >= 7:
        out.append(_dz("sede_gol_" + lado, "🥅", f"{nombre} recibió gol en sus últimos {s_recibe} partidos {tag}",
                       s_recibe * 0.7, {"goles": 1}))
    if s_cero >= 4:
        out.append(_dz("sede_gol_" + lado, "🧤", f"{nombre} no recibe gol {tag} hace {s_cero} partidos",
                       s_cero * 1.2, {"pocos": 1, lado: 0.5}))

    # ---- Tendencias de goles "X de los últimos N" (se elige la mejor por tipo) ----
    for muestra, sufijo in ((sede[:config.VENTANA_TENDENCIA], f" {tag}"),
                            (todos[:config.VENTANA_TENDENCIA], "")):
        n = len(muestra)
        if n < config.MIN_PARTIDOS_TENDENCIA:
            continue
        factor = min(1.0, n / 8)
        x = sum(1 for v in muestra if v["gf"] + v["gc"] > 2.5)
        p = x / n
        if p >= 0.8:
            out.append(_dz("o25_" + lado, "⚽", f"Más de 2.5 goles en {x} de los últimos {n} de {nombre}{sufijo}",
                           _ext(p) * 8 * factor, {"goles": 1}))
        elif p <= 0.2:
            out.append(_dz("o25_" + lado, "🔒", f"Menos de 2.5 goles en {n - x} de los últimos {n} de {nombre}{sufijo}",
                           _ext(p) * 8 * factor, {"pocos": 1}))
        x = sum(1 for v in muestra if v["gf"] > 0 and v["gc"] > 0)
        p = x / n
        if p >= 0.8:
            out.append(_dz("btts_" + lado, "🤝", f"Ambos marcaron en {x} de los últimos {n} de {nombre}{sufijo}",
                           _ext(p) * 7 * factor, {"goles": 1}))
        elif p <= 0.2:
            out.append(_dz("btts_" + lado, "🚫", f"En {n - x} de los últimos {n} de {nombre}{sufijo} no marcaron ambos",
                           _ext(p) * 7 * factor, {"pocos": 1}))
    return out


def datazos_detalle(nombre, eq_id, vs, es_local):
    """1er tiempo, córners y tarjetas usando el detalle de los últimos partidos."""
    lado = "local" if es_local else "visita"
    out = []
    ht, corners, tarjetas = [], [], []
    xg = []   # (xG a favor, xG en contra, goles a favor, goles en contra)
    for v in vs[:config.PARTIDOS_CON_DETALLE]:
        gid = v["p"]["id"]
        d = s365.detalle(gid, terminado=True)
        m = s365.marcador_descanso(d)
        if m:
            ht.append(m[0] + m[1])
        st = s365.estadisticas(gid)
        if st and len(st) == 2 and eq_id in st:
            rival = next(k for k in st if k != eq_id)
            xf, xc = st[eq_id].get("xg"), st[rival].get("xg")
            if xf is not None and xc is not None:
                xg.append((xf, xc, v["gf"], v["gc"]))
        if st and len(st) == 2:
            c = [x.get("corners") for x in st.values()]
            if None not in c:
                corners.append(sum(c))
            t = [x.get("amarillas") for x in st.values()]
            if None not in t:
                rojas = sum(x.get("rojas", 0) or 0 for x in st.values())
                tarjetas.append(sum(t) + rojas)

    n = len(ht)
    if n >= config.MIN_PARTIDOS_TENDENCIA:
        x = sum(1 for g in ht if g >= 1)
        p = x / n
        if p >= 0.85:
            out.append(_dz("ht_" + lado, "⏱️", f"Hubo gol en el 1er tiempo en {x} de los últimos {n} de {nombre}",
                           _ext(p) * 7, {"goles": 1}))
        elif p <= 0.3:
            out.append(_dz("ht_" + lado, "⏱️", f"Se llegó 0-0 al descanso en {n - x} de los últimos {n} de {nombre}",
                           _ext(p) * 7, {"pocos": 1}))

    n = len(corners)
    if n >= config.MIN_PARTIDOS_TENDENCIA:
        x = sum(1 for c in corners if c > 9.5)
        p, prom = x / n, sum(corners) / n
        if p >= 0.8:
            out.append(_dz("corners_" + lado, "🚩",
                           f"Más de 9.5 córners en {x} de los últimos {n} de {nombre} (promedio {prom:.1f})",
                           _ext(p) * 6))
        elif p <= 0.2:
            out.append(_dz("corners_" + lado, "🚩",
                           f"Menos de 9.5 córners en {n - x} de los últimos {n} de {nombre} (promedio {prom:.1f})",
                           _ext(p) * 6))

    n = len(tarjetas)
    if n >= config.MIN_PARTIDOS_TENDENCIA:
        x = sum(1 for c in tarjetas if c > 4.5)
        p, prom = x / n, sum(tarjetas) / n
        if p >= 0.8:
            out.append(_dz("tarjetas_" + lado, "🟨",
                           f"Más de 4.5 tarjetas en {x} de los últimos {n} de {nombre} (promedio {prom:.1f})",
                           _ext(p) * 6))
        elif p <= 0.2:
            out.append(_dz("tarjetas_" + lado, "🟨",
                           f"Menos de 4.5 tarjetas en {n - x} de los últimos {n} de {nombre} (promedio {prom:.1f})",
                           _ext(p) * 6))

    # ---- xG (goles esperados) ----
    resumen_xg = None
    n = len(xg)
    if config.USAR_XG and n >= config.MIN_PARTIDOS_TENDENCIA:
        contra = "visita" if es_local else "local"
        xf = sum(a for a, _, _, _ in xg) / n
        xc = sum(b for _, b, _, _ in xg) / n
        gf = sum(c for _, _, c, _ in xg)
        resumen_xg = {"xg_f": xf, "xg_c": xc, "n": n}
        if xf >= 1.9:
            out.append(_dz("xg_ataque_" + lado, "🎯", f"{nombre} generó {xf:.2f} xG por partido en sus últimos {n}",
                           (xf - 1.3) * 8, {"goles": 1, lado: 0.5}))
        elif xf <= 0.9:
            out.append(_dz("xg_ataque_" + lado, "🎯", f"{nombre} generó solo {xf:.2f} xG por partido en sus últimos {n}",
                           (1.3 - xf) * 9, {"pocos": 1, contra: 0.5}))
        if xc <= 0.8:
            out.append(_dz("xg_defensa_" + lado, "🛡️", f"{nombre} concedió solo {xc:.2f} xG por partido en sus últimos {n}",
                           (1.3 - xc) * 9, {"pocos": 1, lado: 0.5}))
        elif xc >= 1.8:
            out.append(_dz("xg_defensa_" + lado, "🛡️", f"{nombre} concedió {xc:.2f} xG por partido en sus últimos {n}",
                           (xc - 1.3) * 8, {"goles": 1, contra: 0.5}))
        # Suerte: goles reales muy distintos a lo esperado (informativo, no empuja a ningún lado)
        dif = gf - xf * n
        if abs(dif) >= 4:
            como = "por encima" if dif > 0 else "por debajo"
            out.append(_dz("xg_suerte_" + lado, "🍀",
                           f"{nombre} marcó {gf} goles con {xf * n:.1f} xG en sus últimos {n}: rinde {como} de lo esperado",
                           min(abs(dif) * 0.8, 6.5)))
    return out, resumen_xg


# =====================================================================
# Datazos H2H
# =====================================================================
def datazos_h2h(partido, lista):
    L, V = partido["local_id"], partido["visita_id"]
    nombres = {L: partido["local"], V: partido["visita"]}
    H = [p for p in lista if es_valido(p) and {p["local_id"], p["visita_id"]} == {L, V}
         and p["inicio"] and p["inicio"] < partido["inicio"]]
    H.sort(key=lambda x: x["inicio"], reverse=True)
    n = len(H)
    if n < config.MIN_PARTIDOS_H2H:
        return [], H

    hoy = partido["inicio"]
    desde = H[-1]["inicio"].year
    antiguo = desde <= hoy.year - config.ANIOS_H2H_ANTIGUO
    suf = f" (H2H desde {desde}, con otros planteles)" if antiguo else f" (desde {desde})"
    viejo = (hoy - H[0]["inicio"]).days > 4 * 365   # el último cruce es de hace mucho
    castigo = 0.7 if viejo else 1.0
    out = []

    for eq, otro in ((L, V), (V, L)):
        lado_otro = "local" if otro == L else "visita"
        vs = [vista(p, eq) for p in H]
        sg = racha(vs, lambda v: v["res"] != "G")
        if sg >= 4:
            if sg < n:
                ult = vs[sg]["p"]["inicio"]
                paren = f"(último triunfo: {fecha_txt(ult)}"
                if ult.year <= hoy.year - config.ANIOS_H2H_ANTIGUO:
                    paren += ", con otros planteles"
                paren += ")"
            else:
                paren = f"(sin triunfos en los {n} cruces registrados desde {desde})"
            texto = f"{nombres[eq]} lleva {sg} partidos sin ganarle a {nombres[otro]} {paren}"
            out.append(_dz("h2h_racha", "🔥", texto, sg * 1.5 * castigo, {lado_otro: 1},
                           frase=f"{nombres[eq]} lleva {sg} partidos sin ganarle a {nombres[otro]}"))
        w = sum(1 for v in vs if v["res"] == "G")
        if w >= 3 and w / n >= 0.75:
            lado_eq = "local" if eq == L else "visita"
            out.append(_dz("h2h_dominio", "🔥",
                           f"{nombres[eq]} ganó {w} de los últimos {n} enfrentamientos ante {nombres[otro]}{suf}",
                           (w / n) * 8 * castigo, {lado_eq: 1},
                           frase=f"{nombres[eq]} ganó {w} de los últimos {n} cruces"))

    goles = [p["gl"] + p["gv"] for p in H]
    prom = sum(goles) / n
    if prom >= 3.0:
        out.append(_dz("h2h_goles", "💥", f"Promedio de {prom:.1f} goles en los últimos {n} H2H{suf}",
                       (prom - 2.5) * 5 * castigo, {"goles": 1}))
    elif prom <= 1.8:
        out.append(_dz("h2h_goles", "🔒", f"Promedio de solo {prom:.1f} goles en los últimos {n} H2H{suf}",
                       (2.5 - prom) * 5 * castigo, {"pocos": 1}))
    x = sum(1 for p in H if p["gl"] > 0 and p["gv"] > 0)
    if x / n >= 0.8:
        out.append(_dz("h2h_btts", "🤝", f"Ambos marcaron en {x} de los últimos {n} H2H{suf}",
                       _ext(x / n) * 7 * castigo, {"goles": 1}))
    elif x / n <= 0.2:
        out.append(_dz("h2h_btts", "🚫", f"En {n - x} de los últimos {n} H2H no marcaron ambos{suf}",
                       _ext(x / n) * 7 * castigo, {"pocos": 1}))

    # Mismo cruce con el mismo equipo de local
    HL = [p for p in H if p["local_id"] == L]
    m = len(HL)
    if m >= config.MIN_PARTIDOS_H2H:
        vs = [vista(p, L) for p in HL]
        g = sum(1 for v in vs if v["res"] == "G")
        e = sum(1 for v in vs if v["res"] == "E")
        pe = m - g - e
        desde_l = HL[-1]["inicio"].year
        suf_l = (f", desde {desde_l}, con otros planteles" if desde_l <= hoy.year - config.ANIOS_H2H_ANTIGUO
                 else f", desde {desde_l}")
        if pe == 0:
            out.append(_dz("h2h_sede", "🏟️",
                           f"{nombres[L]} no perdió en sus últimos {m} partidos como local ante {nombres[V]} "
                           f"({g}G {e}E{suf_l})", m * 1.2 * castigo, {"local": 1}))
        elif g == 0:
            out.append(_dz("h2h_sede", "🏟️",
                           f"{nombres[L]} no le ganó a {nombres[V]} en sus últimos {m} partidos como local "
                           f"({e}E {pe}P{suf_l})", m * 1.2 * castigo, {"visita": 1}))
    return out, H


# =====================================================================
# Contexto de tabla
# =====================================================================
def datazos_tabla(partido):
    filas = s365.tabla(partido["comp_id"])
    if not filas:
        return []
    por_id = {f["id"]: f for f in filas}
    por_pos = {f["pos"]: f for f in filas}
    fl, fv = por_id.get(partido["local_id"]), por_id.get(partido["visita_id"])
    if not fl or not fv:
        return []
    out = []
    dif = abs(fl["pts"] - fv["pts"])
    if dif >= 9:
        mejor = "local" if fl["pts"] > fv["pts"] else "visita"
        out.append(_dz("tabla", "📊",
                       f"{fl['nombre']} es {fl['pos']}° ({fl['pts']:.0f} pts) y {fv['nombre']} es "
                       f"{fv['pos']}° ({fv['pts']:.0f} pts): {dif:.0f} pts de diferencia",
                       3 + dif * 0.2, {mejor: 0.5}))
    for f in (fl, fv):
        if not f["pj"] or f["pj"] < 3:
            continue
        arriba, abajo = por_pos.get(f["pos"] - 1), por_pos.get(f["pos"] + 1)
        if arriba and arriba["zona"] != f["zona"] and 0 <= arriba["pts"] - f["pts"] <= 3:
            d = arriba["pts"] - f["pts"]
            out.append(_dz("tabla_zona", "📊",
                           f"{f['nombre']} ({f['pos']}°, {f['pts']:.0f} pts) está a {d:.0f} {pl(d, 'punto', 'puntos')} "
                           f"de {arriba['nombre']} ({arriba['pos']}°), en el límite de otra zona de la tabla", 4.5))
        elif abajo and abajo["zona"] != f["zona"] and 0 <= f["pts"] - abajo["pts"] <= 3:
            d = f["pts"] - abajo["pts"]
            out.append(_dz("tabla_zona", "📊",
                           f"{f['nombre']} ({f['pos']}°) tiene solo {d:.0f} {pl(d, 'punto', 'puntos')} de ventaja "
                           f"sobre {abajo['nombre']} ({abajo['pos']}°), en el límite de zona", 4.5))
    return out


# =====================================================================
# Selección y "qué sugiere"
# =====================================================================
def elegir(datazos):
    datazos = [d for d in datazos if d["puntaje"] >= PUNTAJE_MINIMO]
    datazos.sort(key=lambda d: d["puntaje"], reverse=True)
    elegidos, tipos = [], {}
    for d in datazos:
        if tipos.get(d["tipo"], 0) >= 1:     # un datazo por tipo (evita repetir lo mismo)
            continue
        elegidos.append(d)
        tipos[d["tipo"]] = tipos.get(d["tipo"], 0) + 1
        if len(elegidos) >= config.MAX_DATAZOS_POR_PARTIDO:
            break
    return elegidos


def senales(elegidos):
    s = {"local": 0.0, "visita": 0.0, "goles": 0.0, "pocos": 0.0}
    for d in elegidos:
        for k, w in d["lados"].items():
            s[k] += w * d["puntaje"]
    return s


def que_sugiere(s, partido):
    partes = []
    if s["goles"] - s["pocos"] > 3:
        partes.append("tendencia a goles")
    elif s["pocos"] - s["goles"] > 3:
        partes.append("tendencia a pocos goles")
    if s["local"] - s["visita"] > 3:
        partes.append(f"los datos favorecen a {partido['local']}")
    elif s["visita"] - s["local"] > 3:
        partes.append(f"los datos favorecen a {partido['visita']}")
    if not partes:
        partes.append("los datazos no marcan una tendencia clara")
    return "; ".join(partes)


# =====================================================================
# Modelo Poisson
# =====================================================================
def _pois(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def matriz(lh, la, maxg=10):
    ph = [_pois(i, lh) for i in range(maxg + 1)]
    pa = [_pois(j, la) for j in range(maxg + 1)]
    return [[ph[i] * pa[j] for j in range(maxg + 1)] for i in range(maxg + 1)]


def probs_modelo(lh, la):
    M = matriz(lh, la)
    r = range(len(M))

    def suma(cond):
        return sum(M[i][j] for i in r for j in r if cond(i, j))

    p = {
        "1": suma(lambda i, j: i > j),
        "X": suma(lambda i, j: i == j),
        "2": suma(lambda i, j: i < j),
        "BTTS_SI": suma(lambda i, j: i > 0 and j > 0),
        "AH_L-1.5": suma(lambda i, j: i - j >= 2),
        "AH_V-1.5": suma(lambda i, j: j - i >= 2),
    }
    p["1X"] = p["1"] + p["X"]
    p["X2"] = p["2"] + p["X"]
    p["BTTS_NO"] = 1 - p["BTTS_SI"]
    p["AH_L+1.5"] = 1 - p["AH_V-1.5"]
    p["AH_V+1.5"] = 1 - p["AH_L-1.5"]
    for linea in (0.5, 1.5, 2.5, 3.5, 4.5):
        o = suma(lambda i, j, L=linea: i + j > L)
        p[f"O{linea}"] = o
        p[f"U{linea}"] = 1 - o
    return p


def leer_cuotas(lines):
    """Saca las cuotas de Bet365 por código de mercado y las probabilidades sin margen."""
    cuota, mercado = {}, {}

    def opt_odd(o):
        try:
            return float(o["rate"]["decimal"])
        except (KeyError, TypeError, ValueError):
            return None

    for ln in lines:
        t = ln.get("lineTypeId")
        ops = ln.get("options") or []
        if t == 1 and len(ops) == 3:
            od = {o.get("num"): opt_odd(o) for o in ops}
            if all(od.get(k) for k in (1, 2, 3)):
                cuota.update({"1": od[1], "X": od[2], "2": od[3]})
                inv = [1 / od[1], 1 / od[2], 1 / od[3]]
                s = sum(inv)
                mercado.update({"1": inv[0] / s, "X": inv[1] / s, "2": inv[2] / s})
        elif t == 14 and len(ops) == 3:
            od = {o.get("num"): opt_odd(o) for o in ops}
            if all(od.get(k) for k in (1, 2, 3)):
                cuota.update({"1X": od[1], "12": od[2], "X2": od[3]})
                inv = [1 / od[1], 1 / od[2], 1 / od[3]]
                s = sum(inv) / 2       # las tres suman 200% sin margen
                mercado.update({"1X": inv[0] / s, "12": inv[1] / s, "X2": inv[2] / s})
        elif t == 3:
            try:
                linea = float(ln.get("internalOptionValue"))
            except (TypeError, ValueError):
                continue
            over = under = None
            for o in ops:
                nom = (o.get("name") or "").lower()
                if "más" in nom or "mas" in nom or "over" in nom:
                    over = opt_odd(o)
                elif "menos" in nom or "under" in nom:
                    under = opt_odd(o)
            if over and under:
                cuota[f"O{linea}"], cuota[f"U{linea}"] = over, under
                s = 1 / over + 1 / under
                mercado[f"O{linea}"], mercado[f"U{linea}"] = (1 / over) / s, (1 / under) / s
        elif t == 12 and len(ops) == 2:
            od = {o.get("num"): opt_odd(o) for o in ops}
            if od.get(1) and od.get(2):
                cuota["BTTS_SI"], cuota["BTTS_NO"] = od[1], od[2]
                s = 1 / od[1] + 1 / od[2]
                mercado["BTTS_SI"], mercado["BTTS_NO"] = (1 / od[1]) / s, (1 / od[2]) / s
        elif t == 11 and len(ops) == 2:
            loc = next((o for o in ops if o.get("num") == 1), None)
            vis = next((o for o in ops if o.get("num") == 2), None)
            if not loc or not vis:
                continue
            try:
                lead = float(loc.get("lead"))
            except (TypeError, ValueError):
                continue
            if abs(abs(lead) - 1.5) > 1e-6:
                continue
            ol, ov = opt_odd(loc), opt_odd(vis)
            if not ol or not ov:
                continue
            s = 1 / ol + 1 / ov
            if lead < 0:   # Local -1.5 / Visita +1.5
                cuota["AH_L-1.5"], cuota["AH_V+1.5"] = ol, ov
                mercado["AH_L-1.5"], mercado["AH_V+1.5"] = (1 / ol) / s, (1 / ov) / s
            else:          # Local +1.5 / Visita -1.5
                cuota["AH_L+1.5"], cuota["AH_V-1.5"] = ol, ov
                mercado["AH_L+1.5"], mercado["AH_V-1.5"] = (1 / ol) / s, (1 / ov) / s
    return cuota, mercado


def lambdas_mercado(mercado, total_prior):
    """Busca los goles esperados (local, visita) que mejor reproducen las cuotas."""
    if not all(k in mercado for k in ("1", "X", "2")):
        return None
    lineas = sorted({float(k[1:]) for k in mercado if k.startswith("O")}, key=lambda x: abs(x - 2.5))
    linea = lineas[0] if lineas else None

    def error(lh, la):
        M = matriz(lh, la, 8)
        p1 = px = p2 = over = 0.0
        for i, fila in enumerate(M):
            for j, v in enumerate(fila):
                if i > j:
                    p1 += v
                elif i == j:
                    px += v
                else:
                    p2 += v
                if linea is not None and i + j > linea:
                    over += v
        e = (p1 - mercado["1"]) ** 2 + (px - mercado["X"]) ** 2 + (p2 - mercado["2"]) ** 2
        if linea is not None:
            e += (over - mercado[f"O{linea}"]) ** 2
        else:
            e += 0.02 * (lh + la - total_prior) ** 2
        return e

    mejor = (9e9, 1.3, 1.1)
    for i in range(1, 46):            # búsqueda gruesa 0.1 a 4.5
        for j in range(1, 46):
            e = error(i / 10, j / 10)
            if e < mejor[0]:
                mejor = (e, i / 10, j / 10)
    _, bh, ba = mejor
    for i in range(-10, 11):          # búsqueda fina ±0.1
        for j in range(-10, 11):
            lh, la = bh + i / 100, ba + j / 100
            if lh <= 0.05 or la <= 0.05:
                continue
            e = error(lh, la)
            if e < mejor[0]:
                mejor = (e, lh, la)
    return mejor[1], mejor[2]


def lambdas_estadistica(vl, vv, H, partido, xg_l=None, xg_v=None):
    """Goles esperados con forma reciente, local/visita, xG y H2H."""
    def prom(xs, defecto):
        return sum(xs) / len(xs) if xs else defecto

    N = config.VENTANA_TENDENCIA
    l_all, v_all = vl[:N], vv[:N]
    l_home = [v for v in vl if v["local"]][:N]
    v_away = [v for v in vv if not v["local"]][:N]

    def mezcla(sede, todos, campo):
        t = prom([v[campo] for v in todos], 1.3)
        if len(sede) >= 4:
            return 0.5 * prom([v[campo] for v in sede], t) + 0.5 * t
        return t

    ataque_l = mezcla(l_home, l_all, "gf")
    defensa_l = mezcla(l_home, l_all, "gc")
    ataque_v = mezcla(v_away, v_all, "gf")
    defensa_v = mezcla(v_away, v_all, "gc")
    # xG: quita la suerte de los goles reales
    w = config.PESO_XG
    if xg_l:
        ataque_l = (1 - w) * ataque_l + w * xg_l["xg_f"]
        defensa_l = (1 - w) * defensa_l + w * xg_l["xg_c"]
    if xg_v:
        ataque_v = (1 - w) * ataque_v + w * xg_v["xg_f"]
        defensa_v = (1 - w) * defensa_v + w * xg_v["xg_c"]
    lh = (ataque_l + defensa_v) / 2
    la = (ataque_v + defensa_l) / 2

    # H2H reciente (últimos 6 años) con 20% de peso
    recientes = [p for p in H if (partido["inicio"] - p["inicio"]).days < 6 * 365]
    if len(recientes) >= config.MIN_PARTIDOS_H2H:
        gl = prom([p["gl"] if p["local_id"] == partido["local_id"] else p["gv"] for p in recientes], lh)
        gv = prom([p["gv"] if p["local_id"] == partido["local_id"] else p["gl"] for p in recientes], la)
        lh, la = 0.8 * lh + 0.2 * gl, 0.8 * la + 0.2 * gv
    return min(max(lh, 0.2), 4.0), min(max(la, 0.2), 4.0)


LADO_MERCADO = {
    "1": "local", "1X": "local", "AH_L-1.5": "local", "AH_L+1.5": "local",
    "2": "visita", "X2": "visita", "AH_V-1.5": "visita", "AH_V+1.5": "visita",
    "O1.5": "goles", "O2.5": "goles", "O3.5": "goles", "BTTS_SI": "goles",
    "U1.5": "pocos", "U2.5": "pocos", "U3.5": "pocos", "BTTS_NO": "pocos",
}
OPUESTO = {"local": "visita", "visita": "local", "goles": "pocos", "pocos": "goles"}


def descripcion(codigo, partido):
    L, V = partido["local"], partido["visita"]
    d = {
        "1": f"{L} gana", "2": f"{V} gana",
        "1X": f"{L} o empate (doble oportunidad)", "X2": f"{V} o empate (doble oportunidad)",
        "BTTS_SI": "Ambos marcan: Sí", "BTTS_NO": "Ambos marcan: No",
        "AH_L-1.5": f"{L} hándicap -1.5 (gana por 2 o más)",
        "AH_L+1.5": f"{L} hándicap +1.5 (no pierde por 2 o más)",
        "AH_V-1.5": f"{V} hándicap -1.5 (gana por 2 o más)",
        "AH_V+1.5": f"{V} hándicap +1.5 (no pierde por 2 o más)",
    }
    if codigo in d:
        return d[codigo]
    if codigo.startswith("O"):
        return f"Más de {codigo[1:]} goles"
    if codigo.startswith("U"):
        return f"Menos de {codigo[1:]} goles"
    return codigo


def resultado_mercado(codigo, gl, gv):
    """True si la apuesta ganó, False si perdió (con el marcador de 90')."""
    t = gl + gv
    reglas = {
        "1": gl > gv, "X": gl == gv, "2": gv > gl,
        "1X": gl >= gv, "X2": gv >= gl, "12": gl != gv,
        "BTTS_SI": gl > 0 and gv > 0, "BTTS_NO": not (gl > 0 and gv > 0),
        "AH_L-1.5": gl - gv >= 2, "AH_L+1.5": gv - gl < 2,
        "AH_V-1.5": gv - gl >= 2, "AH_V+1.5": gl - gv < 2,
    }
    if codigo in reglas:
        return reglas[codigo]
    if codigo[0] in "OU":
        linea = float(codigo[1:])
        return t > linea if codigo[0] == "O" else t < linea
    return None


def sugerir(partido, s, prob, cuota, mercado):
    """Devuelve (lista de sugerencias, mensaje si no hay)."""
    candidatos = []
    coinciden_fuera_de_rango = False
    hay_senal = any(v > 0 for v in s.values())
    for cod, lado in LADO_MERCADO.items():
        if cod not in cuota or cod not in prob or cod not in mercado:
            continue
        if not (s[lado] > 0 and s[lado] > s[OPUESTO[lado]] and mercado[cod] >= 0.5):
            continue
        odd = cuota[cod]
        if not (config.CUOTA_MINIMA <= odd <= config.CUOTA_MAXIMA):
            coinciden_fuera_de_rango = True
            continue
        p = prob[cod]
        candidatos.append({"codigo": cod, "desc": descripcion(cod, partido), "prob": p,
                           "cuota": odd, "justa": 1 / p, "valor": odd > 1 / p, "ev": p * odd})

    if not candidatos:
        if not hay_senal:
            return [], "Sin sugerencia clara: los datazos no marcan una tendencia"
        if coinciden_fuera_de_rango:
            return [], (f"Sin sugerencia: donde coinciden datos y cuotas, Bet365 paga fuera del rango "
                        f"{config.CUOTA_MINIMA:.2f}–{config.CUOTA_MAXIMA:.2f}")
        return [], "Sin sugerencia clara: los datos y las cuotas no coinciden"

    principales = [c for c in candidatos if c["prob"] >= config.PROB_MINIMA_PRINCIPAL]
    if not principales:
        return [], "Sin sugerencia clara: ninguna opción coincidente es suficientemente probable"
    principal = max(principales, key=lambda c: (c["ev"], c["prob"]))
    principal["tipo"] = "principal"
    out = [principal]
    alts = [c for c in candidatos if c is not principal
            and c["prob"] >= principal["prob"] + config.MEJORA_ALTERNATIVA]
    if alts:
        alt = max(alts, key=lambda c: (c["ev"], c["prob"]))
        alt["tipo"] = "alternativa"
        out.append(alt)
    return out, None


def texto_analisis(partido, elegidos, lh, la, prob):
    # para el análisis se usan los datazos que "apuntan" a algún lado
    frases = [d["frase"] for d in elegidos if d["lados"]][:2]
    if len(frases) == 2:
        # "X ganó... y X marcó..." -> "X ganó... y marcó..."
        for nombre in (partido["local"], partido["visita"]):
            if frases[0].startswith(nombre + " ") and frases[1].startswith(nombre + " "):
                frases[1] = frases[1][len(nombre) + 1:]
                break
    partes = []
    if frases:
        partes.append(" y ".join(frases) + ".")
    total = lh + la
    if total >= 3.0:
        tono = "un partido con goles"
    elif total <= 2.2:
        tono = "un partido cerrado"
    else:
        tono = "un partido con una cantidad de goles normal"
    d = prob["1"] - prob["2"]
    if d > 0.25:
        fav = f", con {partido['local']} como favorito claro"
    elif d < -0.25:
        fav = f", con {partido['visita']} como favorito claro"
    elif abs(d) < 0.1:
        fav = " y parejo"
    else:
        fav = f", con ligera ventaja de {partido['local'] if d > 0 else partido['visita']}"
    partes.append(f"El modelo (75% cuotas, 25% estadística) espera {lh:.1f} a {la:.1f} en goles; "
                  f"los números apuntan a {tono}{fav}.")
    return " ".join(partes)


# =====================================================================
# Todo junto para un partido
# =====================================================================
def analizar_partido(partido):
    print(f"→ {partido['local']} vs {partido['visita']} ({partido['id']})")
    lista_h2h, rec_l, rec_v = s365.h2h(partido["id"])
    hist_l = historial(partido["local_id"], rec_l, partido["inicio"])
    hist_v = historial(partido["visita_id"], rec_v, partido["inicio"])
    vl = [vista(p, partido["local_id"]) for p in hist_l]
    vv = [vista(p, partido["visita_id"]) for p in hist_v]

    todos = []
    todos += datazos_equipo(partido["local"], vl, True)
    todos += datazos_equipo(partido["visita"], vv, False)
    dl, xg_l = datazos_detalle(partido["local"], partido["local_id"], vl, True)
    dv, xg_v = datazos_detalle(partido["visita"], partido["visita_id"], vv, False)
    todos += dl + dv
    # H2H: lo que trae 365Scores + cruces que aparezcan en el historial largo de cada equipo
    extra = [p for p in hist_l + hist_v
             if {p["local_id"], p["visita_id"]} == {partido["local_id"], partido["visita_id"]}]
    vistos, lista = set(), []
    for p in lista_h2h + extra:
        if p["id"] not in vistos:
            vistos.add(p["id"])
            lista.append(p)
    dz_h2h, H = datazos_h2h(partido, lista)
    todos += dz_h2h
    try:
        todos += datazos_tabla(partido)
    except Exception as e:  # noqa: BLE001
        print("  ! tabla:", e)

    elegidos = elegir(todos)
    s = senales(elegidos)
    try:
        bajas = s365.bajas(partido["id"])
    except Exception as e:  # noqa: BLE001
        print("  ! bajas:", e)
        bajas = None
    res = {"partido": partido, "datazos": elegidos, "todos": todos,
           "sugiere": que_sugiere(s, partido), "senales": s, "bajas": bajas,
           "analisis": None, "sugerencias": [], "sin_sugerencia": None, "lambdas": None}

    # ---- Análisis con cuotas ----
    cuota, mercado = leer_cuotas(s365.cuotas(partido["id"]))
    if len(vl) < config.MIN_PARTIDOS_TENDENCIA or len(vv) < config.MIN_PARTIDOS_TENDENCIA:
        res["sin_sugerencia"] = "Sin sugerencia: pocos partidos recientes para el modelo"
        return res
    lh_s, la_s = lambdas_estadistica(vl, vv, H, partido, xg_l, xg_v)
    lm = lambdas_mercado(mercado, lh_s + la_s)
    if not lm:
        res["sin_sugerencia"] = "Sin sugerencia: 365Scores no trae cuotas 1X2 de Bet365 para este partido"
        return res
    w = config.PESO_MERCADO
    lh = w * lm[0] + (1 - w) * lh_s
    la = w * lm[1] + (1 - w) * la_s
    prob = probs_modelo(lh, la)
    res["lambdas"] = (lh, la)
    res["analisis"] = texto_analisis(partido, elegidos, lh, la, prob)
    if bajas:
        for lado, nombre in (("local", partido["local"]), ("visita", partido["visita"])):
            clave = [j for j in bajas[lado] if j["goles"] >= 5]
            if clave:
                j = clave[0]
                res["analisis"] += (f" Ojo: {nombre} no tendría a {j['nombre']} ({j['goles']} goles); "
                                    f"las cuotas ya suelen reflejarlo.")
    res["sugerencias"], res["sin_sugerencia"] = sugerir(partido, s, prob, cuota, mercado)
    return res


# =====================================================================
# Formato del mensaje (HTML de Telegram)
# =====================================================================
def _e(t):
    return html.escape(str(t), quote=False)


def linea_sugerencia(c):
    marca = ("✅ hay valor" if c["valor"]
             else "ℹ️ sin valor a esta cuota (la casa paga menos de lo que vale)")
    return (f"{_e(c['desc'])} · prob. {c['prob'] * 100:.0f}% · Bet365 {c['cuota']:.2f} · "
            f"justa {c['justa']:.2f} {marca}")


def texto_bajas(bajas, p, max_por_equipo=4):
    """'🚑 Bajas: Barcelona — Raphinha (12 goles, lesión en el muslo), Christensen y 2 más'."""
    if not bajas or not (bajas["local"] or bajas["visita"]):
        return None
    partes = []
    for lado, nombre in (("local", p["local"]), ("visita", p["visita"])):
        js = bajas[lado]
        if not js:
            continue
        items = []
        for j in js[:max_por_equipo]:
            extra = []
            if j["goles"]:
                extra.append(f"{j['goles']} {pl(j['goles'], 'gol', 'goles')}")
            if j["asist"] >= 3:
                extra.append(f"{j['asist']} asist.")
            if extra:
                extra.append(j["motivo"].lower())
                items.append(f"{j['nombre']} ({', '.join(extra)})")
            else:
                items.append(j["nombre"])
        resto = len(js) - max_por_equipo
        txt = ", ".join(items) + (f" y {resto} más" if resto > 0 else "")
        partes.append(f"{nombre} — {txt}")
    estado = "" if bajas.get("confirmadas") else " · <i>según 365Scores, alineación aún sin confirmar</i>"
    return "🚑 <b>Bajas:</b> " + _e(" | ".join(partes)) + estado


def formatear(res, nombre_liga):
    p = res["partido"]
    hora = p["inicio"].strftime("%H:%M") if p["inicio"] else "?"
    lineas = [f"⚽ <b>{_e(p['local'])} vs {_e(p['visita'])}</b> · {_e(nombre_liga)} · 🕐 {hora}"]
    if res["datazos"]:
        for d in res["datazos"]:
            lineas.append(f"{d['emoji']} {_e(d['texto'])}")
    else:
        lineas.append("— Sin datazos llamativos con muestra suficiente —")
    linea_b = texto_bajas(res.get("bajas"), p)
    if linea_b:
        lineas.append(linea_b)
    lineas.append(f"🧭 <b>Qué sugiere:</b> {_e(res['sugiere'])}. "
                  f"<i>Las rachas no garantizan nada y el mercado ya suele tenerlas en cuenta.</i>")
    if res["analisis"]:
        lineas.append(f"📝 <b>Análisis:</b> {_e(res['analisis'])}")
    for c in res["sugerencias"]:
        titulo = "Sugerencia principal" if c["tipo"] == "principal" else "Alternativa más segura"
        lineas.append(f"🎯 <b>{titulo}:</b> {linea_sugerencia(c)}")
    if res["sin_sugerencia"]:
        lineas.append(f"🎯 {_e(res['sin_sugerencia'])}")
    return "\n".join(lineas)
