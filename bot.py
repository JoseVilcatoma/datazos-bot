# -*- coding: utf-8 -*-
"""
BOT DE DATAZOS — punto de entrada.

Uso:
  python bot.py                     -> modo automático (lo que corre GitHub Actions)
  python bot.py --modo manana       -> manda ya los datazos de mañana
  python bot.py --modo hoy          -> manda ya los datazos de hoy
  python bot.py --modo resumen      -> manda el resumen de aciertos
  python bot.py --probar 4828481    -> imprime los datazos de ese partido SIN enviar nada
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config
import datazos
import s365

TZ = ZoneInfo(config.ZONA_HORARIA)
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
COLUMNAS = ["registrado", "game_id", "fecha_partido", "partido", "liga", "tipo", "mercado",
            "descripcion", "prob", "cuota", "cuota_justa", "valor", "estado",
            "goles_local", "goles_visita"]


# =====================================================================
# Archivos de estado
# =====================================================================
def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return defecto


def guardar_json(ruta, data):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def leer_csv():
    if not os.path.exists(config.ARCHIVO_SUGERENCIAS):
        return []
    with open(config.ARCHIVO_SUGERENCIAS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def guardar_csv(filas):
    os.makedirs(os.path.dirname(config.ARCHIVO_SUGERENCIAS), exist_ok=True)
    with open(config.ARCHIVO_SUGERENCIAS, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        for r in filas:
            w.writerow({k: r.get(k, "") for k in COLUMNAS})


# =====================================================================
# Telegram
# =====================================================================
def tg(metodo, **kw):
    if not TOKEN:
        print("  ! Falta TELEGRAM_TOKEN")
        return None
    url = f"https://api.telegram.org/bot{TOKEN}/{metodo}"
    for intento in range(3):
        try:
            r = requests.post(url, json=kw, timeout=30)
            data = r.json()
            if data.get("ok"):
                return data.get("result")
            if r.status_code == 429:
                espera = data.get("parameters", {}).get("retry_after", 5)
                time.sleep(espera + 1)
                continue
            print("  ! Telegram:", data.get("description"))
            return None
        except Exception as e:  # noqa: BLE001
            print("  ! Telegram error:", e)
            time.sleep(3 * (intento + 1))
    return None


def enviar(texto):
    """Envía un mensaje HTML (lo parte si es muy largo)."""
    if not CHAT_ID:
        print("  ! Falta TELEGRAM_CHAT_ID")
        return
    trozos = []
    while len(texto) > 4000:
        corte = texto.rfind("\n", 0, 4000)
        corte = corte if corte > 0 else 4000
        trozos.append(texto[:corte])
        texto = texto[corte:]
    trozos.append(texto)
    for t in trozos:
        tg("sendMessage", chat_id=CHAT_ID, text=t, parse_mode="HTML",
           disable_web_page_preview=True)
        time.sleep(1.2)


# =====================================================================
# Partidos del día
# =====================================================================
def partidos_del_dia(fecha, excluir=()):
    lista = s365.partidos_por_fecha(fecha, config.LIGAS_ACTIVAS)
    lista = [p for p in lista if p["estado"] in (1, 2)]      # aún no empiezan
    lista = [p for p in lista if str(p["id"]) not in excluir]  # quitar ya enviados ANTES del límite
    prioridad = {c: i for i, c in enumerate(config.LIGAS_ACTIVAS)}
    lista.sort(key=lambda p: (prioridad.get(p["comp_id"], 99), p["inicio"]))
    lista = lista[:config.MAX_PARTIDOS]
    lista.sort(key=lambda p: p["inicio"])                     # el mensaje va por hora
    return lista


def nombre_liga(p):
    return config.LIGAS.get(p["comp_id"], p["comp_nombre"])


def registrar_sugerencias(res):
    if not res["sugerencias"]:
        return
    filas = leer_csv()
    existentes = {(r["game_id"], r["tipo"]) for r in filas}
    p = res["partido"]
    ahora = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    for c in res["sugerencias"]:
        clave = (str(p["id"]), c["tipo"])
        if clave in existentes:
            continue
        filas.append({
            "registrado": ahora, "game_id": p["id"],
            "fecha_partido": p["inicio"].isoformat(),
            "partido": f"{p['local']} vs {p['visita']}", "liga": nombre_liga(p),
            "tipo": c["tipo"], "mercado": c["codigo"], "descripcion": c["desc"],
            "prob": f"{c['prob']:.4f}", "cuota": f"{c['cuota']:.2f}",
            "cuota_justa": f"{c['justa']:.2f}", "valor": "si" if c["valor"] else "no",
            "estado": "pendiente", "goles_local": "", "goles_visita": "",
        })
    guardar_csv(filas)


def enviar_dia(fecha, etiqueta, forzar=False):
    enviados = leer_json(config.ARCHIVO_ENVIADOS, {})
    partidos = partidos_del_dia(fecha, excluir=() if forzar else set(enviados))
    if not partidos:
        ya = [p for p in s365.partidos_por_fecha(fecha, config.LIGAS_ACTIVAS)
              if str(p["id"]) in enviados]
        if ya:
            fechas = sorted({enviados[str(p["id"])] for p in ya})
            cuando = ", ".join(datetime.strptime(f, "%Y-%m-%d").strftime("%d/%m") for f in fechas)
            enviar(f"📅 Los {len(ya)} partidos de {etiqueta} ({fecha.strftime('%d/%m')}) ya te los mandé "
                   f"antes (el {cuando}). Si los quieres de nuevo escribe /datazos "
                   f"{'hoy' if etiqueta == 'hoy' else 'mañana'}.")
        else:
            enviar(f"📅 No hay partidos de las ligas elegidas para {etiqueta} ({fecha.strftime('%d/%m')}).")
        return
    enviar(f"📅 <b>Datazos de {etiqueta}</b> ({fecha.strftime('%d/%m')}) · "
           f"{len(partidos)} {datazos.pl(len(partidos), 'partido', 'partidos')}")
    for p in partidos:
        try:
            res = datazos.analizar_partido(p)
            enviar(datazos.formatear(res, nombre_liga(p)))
            registrar_sugerencias(res)
            enviados[str(p["id"])] = datetime.now(TZ).strftime("%Y-%m-%d")
            guardar_json(config.ARCHIVO_ENVIADOS, enviados)
            seg = leer_json(config.ARCHIVO_SEGUIMIENTO, {})
            seg.setdefault(str(p["id"]), {"inicio": p["inicio"].isoformat(), "reportado": False})
            guardar_json(config.ARCHIVO_SEGUIMIENTO, seg)
        except Exception as e:  # noqa: BLE001
            print(f"  ! Error con {p['local']} vs {p['visita']}: {e}")


def limpiar_enviados():
    enviados = leer_json(config.ARCHIVO_ENVIADOS, {})
    limite = (datetime.now(TZ) - timedelta(days=30)).strftime("%Y-%m-%d")
    nuevos = {k: v for k, v in enviados.items() if v >= limite}
    if len(nuevos) != len(enviados):
        guardar_json(config.ARCHIVO_ENVIADOS, nuevos)


# =====================================================================
# Calificar sugerencias y resumen
# =====================================================================
def calificar_pendientes():
    filas = leer_csv()
    ahora = datetime.now(TZ)
    cambio = False
    for r in filas:
        if r["estado"] != "pendiente":
            continue
        try:
            inicio = datetime.fromisoformat(r["fecha_partido"])
        except ValueError:
            continue
        if ahora < inicio + timedelta(hours=config.HORAS_PARA_RESULTADO):
            continue
        g = s365.detalle(r["game_id"], terminado=False)
        if g and g.get("statusGroup") == 4:
            m = s365.marcador_90(g)
            if m:
                ok = datazos.resultado_mercado(r["mercado"], m[0], m[1])
                r["estado"] = "acierto" if ok else "fallo"
                r["goles_local"], r["goles_visita"] = m
                cambio = True
                print(f"  ✔ {r['partido']}: {r['descripcion']} -> {r['estado']}")
        elif ahora > inicio + timedelta(days=3):
            r["estado"] = "nula"      # suspendido / sin resultado
            cambio = True
    if cambio:
        guardar_csv(filas)


def _linea_stats(st, local_id, visita_id):
    """'xG 0.9–2.4 · córners 4–7 · tarjetas 3–2' con lo que haya."""
    if not st or local_id not in st or visita_id not in st:
        return ""
    L, V = st[local_id], st[visita_id]
    partes = []
    if L.get("xg") is not None and V.get("xg") is not None:
        partes.append(f"xG {L['xg']:.1f}–{V['xg']:.1f}")
    if L.get("corners") is not None and V.get("corners") is not None:
        partes.append(f"córners {L['corners']:.0f}–{V['corners']:.0f}")
    if L.get("amarillas") is not None and V.get("amarillas") is not None:
        tl = L["amarillas"] + (L.get("rojas") or 0)
        tv = V["amarillas"] + (V.get("rojas") or 0)
        partes.append(f"tarjetas {tl:.0f}–{tv:.0f}")
    return " · ".join(partes)


def reportar_terminados():
    """Manda el resultado de los partidos que el bot envió y ya terminaron."""
    seg = leer_json(config.ARCHIVO_SEGUIMIENTO, {})
    enviados = leer_json(config.ARCHIVO_ENVIADOS, {})
    ahora = datetime.now(TZ)
    S = config.STAKE_SIMULADO

    # Partidos enviados antes de esta versión: se agregan al seguimiento (solo los recientes)
    limite = (ahora - timedelta(days=2)).strftime("%Y-%m-%d")
    for gid, fecha in enviados.items():
        if gid not in seg and fecha >= limite:
            g = s365.detalle(gid)
            p = s365.normalizar(g) if g else None
            if p and p["inicio"]:
                seg[gid] = {"inicio": p["inicio"].isoformat(), "reportado": False}

    por_juego = {}
    for r in leer_csv():
        por_juego.setdefault(r["game_id"], []).append(r)

    bloques, n_ac, n_tot, ganancia = [], 0, 0, 0.0
    for gid, info in sorted(seg.items(), key=lambda kv: kv[1]["inicio"]):
        if info.get("reportado"):
            continue
        inicio = datetime.fromisoformat(info["inicio"])
        if ahora < inicio + timedelta(hours=config.HORAS_PARA_RESULTADO):
            continue
        sugs = por_juego.get(gid, [])
        if any(r["estado"] == "pendiente" for r in sugs):
            continue                      # espera a que se califique la sugerencia
        g = s365.detalle(gid)
        if not g:
            continue
        if g.get("statusGroup") != 4:
            if ahora > inicio + timedelta(days=2):
                info["reportado"] = True  # suspendido o sin resultado
            continue
        p = s365.normalizar(g)
        m90 = s365.marcador_90(g)
        marcador = f"{p['gl']}-{p['gv']}" if p["gl"] is not None else "?"
        extra = ""
        if m90 and (m90[0], m90[1]) != (p["gl"], p["gv"]):
            extra = f" (90': {m90[0]}-{m90[1]})"
        if g.get("winDescription"):
            extra += f" · {g['winDescription']}"
        lineas = [f"⚽ <b>{datazos._e(p['local'])} {marcador} {datazos._e(p['visita'])}</b>{datazos._e(extra)}"
                  f" · {datazos._e(nombre_liga(p))}"]
        try:
            st = _linea_stats(s365.estadisticas(gid), p["local_id"], p["visita_id"])
        except Exception:  # noqa: BLE001
            st = ""
        if st:
            lineas.append(f"   📊 {st}")
        if not sugs:
            lineas.append("   🎯 No hubo sugerencia")
        for r in sugs:
            if r["estado"] == "acierto":
                gan = (float(r["cuota"]) - 1) * S
                txt = f"✅ acierto · +S/ {gan:.2f}"
                n_ac += 1
            elif r["estado"] == "fallo":
                gan = -S
                txt = f"❌ fallo · -S/ {S:.2f}"
            else:
                gan = 0
                txt = "➖ nula (sin resultado)"
            if r["estado"] in ("acierto", "fallo"):
                n_tot += 1
                ganancia += gan
            tipo = "🎯" if r["tipo"] == "principal" else "🛟"
            lineas.append(f"   {tipo} {datazos._e(r['descripcion'])} ({r['cuota']}) → {txt}")
        bloques.append("\n".join(lineas))
        info["reportado"] = True

    # limpiar seguimiento viejo
    corte = ahora - timedelta(days=30)
    seg = {k: v for k, v in seg.items()
           if not (v.get("reportado") and datetime.fromisoformat(v["inicio"]) < corte)}
    guardar_json(config.ARCHIVO_SEGUIMIENTO, seg)

    if bloques:
        pie = ""
        if n_tot:
            pie = (f"\n\n📈 En este lote: {n_ac}/{n_tot} sugerencias acertadas · "
                   f"S/ {ganancia:+.2f} (S/ {S} c/u). Escribe /resumen para el acumulado.")
        enviar("🏁 <b>Resultados</b>\n\n" + "\n\n".join(bloques) + pie)
    return len(bloques)


def texto_resumen():
    filas = leer_csv()
    hechas = [r for r in filas if r["estado"] in ("acierto", "fallo")]
    pend = sum(1 for r in filas if r["estado"] == "pendiente")
    if not hechas:
        return f"📊 Todavía no hay sugerencias terminadas. Pendientes: {pend}."
    S = config.STAKE_SIMULADO

    def bloque(rs, titulo):
        if not rs:
            return f"<b>{titulo}</b>: sin datos"
        n = len(rs)
        ac = sum(1 for r in rs if r["estado"] == "acierto")
        esp = sum(float(r["prob"]) for r in rs)
        gan = sum((float(r["cuota"]) - 1) * S if r["estado"] == "acierto" else -S for r in rs)
        return (f"<b>{titulo}</b>: {ac}/{n} aciertos ({ac / n * 100:.0f}%) · esperados {esp:.1f} "
                f"({esp / n * 100:.0f}%) · ganancia simulada S/ {gan:+.2f} (ROI {gan / (n * S) * 100:+.1f}%)")

    lineas = ["📊 <b>Resumen de sugerencias</b> (S/ %d a cada una)" % S,
              bloque(hechas, "Todas"),
              bloque([r for r in hechas if r["tipo"] == "principal"], "Principales"),
              bloque([r for r in hechas if r["tipo"] == "alternativa"], "Alternativas"),
              bloque([r for r in hechas if r["valor"] == "si"], "Con ✅ valor"),
              f"Pendientes: {pend}"]
    if len(hechas) < 50:
        lineas.append("<i>Ojo: con menos de 50 apuestas el resultado es mayormente suerte.</i>")
    return "\n".join(lineas)


# =====================================================================
# Comandos de Telegram (se leen con getUpdates en cada corrida)
# =====================================================================
AYUDA = ("🤖 <b>Comandos</b>\n/datazos hoy — datazos de hoy\n/datazos mañana — datazos de mañana\n"
         "/resultados — resultados de partidos recién terminados\n"
         "/resumen — aciertos vs probabilidad esperada\n"
         "<i>El bot revisa los comandos cada ~15 min (GitHub Actions), no al instante.</i>")


def procesar_comandos(estado):
    offset = estado.get("offset", 0)
    updates = tg("getUpdates", offset=offset, timeout=0) or []
    for u in updates:
        estado["offset"] = u["update_id"] + 1
        msg = u.get("message") or u.get("channel_post") or {}
        if str((msg.get("chat") or {}).get("id")) != CHAT_ID:
            continue                       # solo obedece a tu chat
        texto = (msg.get("text") or "").strip().lower()
        texto = re.sub(r"@\w+", "", texto)  # quita "@nombrebot"
        hoy = datetime.now(TZ).date()
        if texto.startswith("/datazos"):
            if "hoy" in texto:
                enviar("⏳ Calculando datazos de hoy...")
                enviar_dia(hoy, "hoy", forzar=True)
            elif datetime.now(TZ).hour < 5:
                # pasada la medianoche, "mañana" casi siempre significa el día que empieza
                if "pasado" in texto:
                    enviar("⏳ Calculando datazos del día siguiente...")
                    enviar_dia(hoy + timedelta(days=1), "mañana", forzar=True)
                else:
                    enviar("⏳ Ya pasó la medianoche: te mando los partidos de HOY "
                           f"({hoy.strftime('%d/%m')}). Para el día siguiente escribe /datazos pasado")
                    enviar_dia(hoy, "hoy", forzar=True)
            elif "pasado" in texto:
                enviar("⏳ Calculando datazos de pasado mañana...")
                enviar_dia(hoy + timedelta(days=2), "pasado mañana", forzar=True)
            else:
                enviar("⏳ Calculando datazos de mañana...")
                enviar_dia(hoy + timedelta(days=1), "mañana", forzar=True)
        elif texto.startswith("/resultados"):
            calificar_pendientes()
            if not reportar_terminados():
                enviar("🏁 No hay partidos terminados nuevos. Los que ya terminaron te llegaron antes; "
                       "escribe /resumen para el acumulado.")
        elif texto.startswith("/resumen"):
            calificar_pendientes()
            enviar(texto_resumen())
        elif texto.startswith("/start") or texto.startswith("/ayuda") or texto.startswith("/help"):
            enviar(AYUDA)
    guardar_json(config.ARCHIVO_ESTADO, estado)


# =====================================================================
# Modo prueba
# =====================================================================
def probar(game_id):
    g = s365.detalle(game_id)
    if not g:
        print("No encontré ese partido en 365Scores.")
        return
    p = s365.normalizar(g)
    res = datazos.analizar_partido(p)
    texto = datazos.formatear(res, nombre_liga(p))
    print("\n" + "=" * 70)
    print(re.sub(r"</?(b|i)>", "", texto))
    print("=" * 70)
    print("\nTodos los datazos candidatos (puntaje):")
    for d in sorted(res["todos"], key=lambda d: -d["puntaje"]):
        marca = "✓" if d in res["datazos"] else " "
        print(f"  {marca} {d['puntaje']:5.1f}  {d['texto']}")
    print("\nSeñales:", {k: round(v, 1) for k, v in res["senales"].items()})
    if res["lambdas"]:
        print("Goles esperados: %.2f - %.2f" % res["lambdas"])
    print("(Modo prueba: no se envió nada ni se guardó nada.)")


# =====================================================================
# Main
# =====================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", default="auto", choices=["auto", "hoy", "manana", "resumen"])
    ap.add_argument("--probar", type=int, help="id de partido de 365Scores")
    args = ap.parse_args()

    if args.probar:
        probar(args.probar)
        return

    s365.limpiar_cache()
    estado = leer_json(config.ARCHIVO_ESTADO, {})
    ahora = datetime.now(TZ)
    hoy = ahora.date()
    print("Hora Lima:", ahora.strftime("%Y-%m-%d %H:%M"))

    if args.modo == "hoy":
        enviar_dia(hoy, "hoy", forzar=True)
    elif args.modo == "manana":
        enviar_dia(hoy + timedelta(days=1), "mañana", forzar=True)
    elif args.modo == "resumen":
        calificar_pendientes()
        enviar(texto_resumen())
    else:
        procesar_comandos(estado)
        calificar_pendientes()
        reportar_terminados()
        if ahora.hour >= config.HORA_ENVIO_DIARIO and estado.get("ultimo_diario") != hoy.isoformat():
            enviar_dia(hoy + timedelta(days=1), "mañana")
            estado["ultimo_diario"] = hoy.isoformat()
        limpiar_enviados()

    guardar_json(config.ARCHIVO_ESTADO, estado)


if __name__ == "__main__":
    if not TOKEN and "--probar" not in sys.argv:
        print("Aviso: no hay TELEGRAM_TOKEN; los mensajes no se enviarán.")
    main()
