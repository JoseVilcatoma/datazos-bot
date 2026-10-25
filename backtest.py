# -*- coding: utf-8 -*-
"""
BACKTEST de las reglas de sugerencia con datos históricos GRATIS de football-data.co.uk.

Responde dos preguntas:
  1) ¿Las sugerencias habrían ganado plata en temporadas pasadas?
  2) ¿Le ganan a la cuota de CIERRE de Pinnacle (CLV)? Es el mejor indicador de largo plazo:
     si sistemáticamente consigues mejor precio que el cierre de Pinnacle, tienes ventaja real.

Además compara contra una "línea base" (apostar al mismo tipo de mercado SIN mirar los
datazos) para saber si los datazos agregan algo o solo adornan.

Uso:
  python backtest.py               -> imprime el resumen y guarda data/backtest.csv
  python backtest.py --telegram    -> además manda el resumen a Telegram

Limitaciones: football-data solo trae ligas (no copas ni Champions), y sus cuotas útiles son
1X2 y más/menos 2.5; por eso el backtest prueba solo esos mercados y no usa xG ni bajas.
"""
import argparse
import csv
import io
import os
import time
from datetime import datetime

import requests

import config
import datazos as dz

URL = "https://www.football-data.co.uk/mmz4281/{temp}/{div}.csv"
CARPETA = os.path.join(config.CARPETA_CACHE, "footballdata")


# =====================================================================
# Descarga y lectura
# =====================================================================
def descargar(temp, div):
    os.makedirs(CARPETA, exist_ok=True)
    ruta = os.path.join(CARPETA, f"{temp}_{div}.csv")
    actual = temp == config.BACKTEST_TEMPORADAS[-1]
    if os.path.exists(ruta) and (not actual or time.time() - os.path.getmtime(ruta) < 86400):
        with open(ruta, encoding="utf-8") as f:
            return f.read()
    url = URL.format(temp=temp, div=div)
    for intento in range(3):
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code == 404:
                print(f"  - {temp}/{div}: no existe")
                return ""
            r.raise_for_status()
            texto = r.content.decode("utf-8-sig", errors="replace")
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(texto)
            return texto
        except Exception as e:  # noqa: BLE001
            print(f"  ! {url}: {e}")
            time.sleep(3 * (intento + 1))
    return ""


def _f(fila, *claves):
    """Primer número válido entre varias columnas posibles."""
    for c in claves:
        v = (fila.get(c) or "").strip()
        if v:
            try:
                x = float(v)
                if x > 1.0:
                    return x
            except ValueError:
                pass
    return None


def _fecha(fila):
    d = (fila.get("Date") or "").strip()
    t = (fila.get("Time") or "12:00").strip() or "12:00"
    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            return datetime.strptime(f"{d} {t}", fmt)
        except ValueError:
            continue
    return None


def leer_liga(div, nombre):
    partidos = []
    for temp in config.BACKTEST_TEMPORADAS:
        texto = descargar(temp, div)
        if not texto:
            continue
        for i, f in enumerate(csv.DictReader(io.StringIO(texto))):
            ini = _fecha(f)
            try:
                gl, gv = int(f["FTHG"]), int(f["FTAG"])
            except (KeyError, ValueError, TypeError):
                continue
            if not ini or not f.get("HomeTeam") or not f.get("AwayTeam"):
                continue
            partidos.append({
                "id": f"{div}-{temp}-{i}", "comp_id": div, "comp_nombre": nombre, "inicio": ini,
                "estado": 4, "estado_txt": "", "local_id": f["HomeTeam"].strip(), "local": f["HomeTeam"].strip(),
                "visita_id": f["AwayTeam"].strip(), "visita": f["AwayTeam"].strip(), "gl": gl, "gv": gv,
                # Cuotas Bet365 (como el bot en vivo) y cierre de Pinnacle (para medir CLV)
                "b365": {"1": _f(f, "B365H"), "X": _f(f, "B365D"), "2": _f(f, "B365A"),
                         "O2.5": _f(f, "B365>2.5"), "U2.5": _f(f, "B365<2.5")},
                "pin": {"1": _f(f, "PSCH", "PSH"), "X": _f(f, "PSCD", "PSD"), "2": _f(f, "PSCA", "PSA"),
                        "O2.5": _f(f, "PC>2.5", "P>2.5"), "U2.5": _f(f, "PC<2.5", "P<2.5")},
            })
    partidos.sort(key=lambda p: p["inicio"])
    return partidos


def sin_margen(od):
    """Probabilidades sin margen para 1X2 y más/menos 2.5."""
    out = {}
    if od.get("1") and od.get("X") and od.get("2"):
        s = 1 / od["1"] + 1 / od["X"] + 1 / od["2"]
        out.update({k: (1 / od[k]) / s for k in ("1", "X", "2")})
    if od.get("O2.5") and od.get("U2.5"):
        s = 1 / od["O2.5"] + 1 / od["U2.5"]
        out.update({k: (1 / od[k]) / s for k in ("O2.5", "U2.5")})
    return out


# =====================================================================
# Simulación
# =====================================================================
def linea_base(prob, cuota, mercado):
    """Lo mismo que el bot pero SIN exigir que los datazos coincidan."""
    cands = []
    for cod in dz.LADO_MERCADO:
        if cod in cuota and cod in prob and cod in mercado and mercado[cod] >= 0.5:
            if config.CUOTA_MINIMA <= cuota[cod] <= config.CUOTA_MAXIMA and prob[cod] >= config.PROB_MINIMA_PRINCIPAL:
                cands.append((prob[cod] * cuota[cod], prob[cod], cod))
    return max(cands)[2] if cands else None


def simular():
    filas, base = [], []
    for div, nombre in config.BACKTEST_LIGAS.items():
        partidos = leer_liga(div, nombre)
        print(f"{nombre}: {len(partidos)} partidos")
        hist = {}
        for p in partidos:
            L, V = p["local_id"], p["visita_id"]
            hl, hv = hist.get(L, []), hist.get(V, [])
            cuota = {k: v for k, v in p["b365"].items() if v}
            if len(hl) >= config.MIN_PARTIDOS_TENDENCIA and len(hv) >= config.MIN_PARTIDOS_TENDENCIA and cuota:
                vl = [dz.vista(x, L) for x in hl]
                vv = [dz.vista(x, V) for x in hv]
                todos = dz.datazos_equipo(p["local"], vl, True) + dz.datazos_equipo(p["visita"], vv, False)
                cruces = [x for x in hl if {x["local_id"], x["visita_id"]} == {L, V}]
                dzh, H = dz.datazos_h2h(p, cruces)
                todos += dzh
                elegidos = dz.elegir(todos)
                s = dz.senales(elegidos)
                mercado = sin_margen(cuota)
                lh_s, la_s = dz.lambdas_estadistica(vl, vv, H, p)
                lm = dz.lambdas_mercado(mercado, lh_s + la_s)
                if lm:
                    w = config.PESO_MERCADO
                    lh, la = w * lm[0] + (1 - w) * lh_s, w * lm[1] + (1 - w) * la_s
                    prob = dz.probs_modelo(lh, la)
                    pin = sin_margen(p["pin"])
                    sugs, _ = dz.sugerir(p, s, prob, cuota, mercado)
                    for c in sugs:
                        gano = dz.resultado_mercado(c["codigo"], p["gl"], p["gv"])
                        clv = c["cuota"] * pin[c["codigo"]] - 1 if c["codigo"] in pin else None
                        filas.append({
                            "fecha": p["inicio"].strftime("%Y-%m-%d"), "liga": nombre,
                            "partido": f"{L} vs {V}", "marcador": f"{p['gl']}-{p['gv']}",
                            "tipo": c["tipo"], "mercado": c["codigo"], "prob": round(c["prob"], 4),
                            "cuota": c["cuota"], "valor": "si" if c["valor"] else "no",
                            "acierto": int(gano), "clv": "" if clv is None else round(clv, 4),
                        })
                    cod = linea_base(prob, cuota, mercado)
                    if cod:
                        gano = dz.resultado_mercado(cod, p["gl"], p["gv"])
                        clv = cuota[cod] * pin[cod] - 1 if cod in pin else None
                        base.append({"cuota": cuota[cod], "prob": prob[cod], "acierto": int(gano), "clv": clv})
            # el partido entra al historial DESPUÉS de analizarlo (sin mirar el futuro)
            hist.setdefault(L, []).insert(0, p)
            hist.setdefault(V, []).insert(0, p)
    return filas, base


# =====================================================================
# Resumen
# =====================================================================
def bloque(rs, titulo):
    S = config.STAKE_SIMULADO
    if not rs:
        return f"<b>{titulo}</b>: sin datos"
    n = len(rs)
    ac = sum(r["acierto"] for r in rs)
    esp = sum(float(r["prob"]) for r in rs)
    gan = sum((float(r["cuota"]) - 1) * S if r["acierto"] else -S for r in rs)
    clvs = [float(r["clv"]) for r in rs if r.get("clv") not in ("", None)]
    txt_clv = ""
    if clvs:
        pos = sum(1 for c in clvs if c > 0) / len(clvs)
        txt_clv = f" · CLV medio {sum(clvs) / len(clvs) * 100:+.1f}% ({pos * 100:.0f}% le gana al cierre)"
    return (f"<b>{titulo}</b>: {n} apuestas · {ac / n * 100:.1f}% aciertos (esperado {esp / n * 100:.1f}%) · "
            f"S/ {gan:+.0f} · ROI {gan / (n * S) * 100:+.1f}%{txt_clv}")


def resumen(filas, base):
    lin = ["🧪 <b>Backtest</b> (football-data, temporadas " + ", ".join(config.BACKTEST_TEMPORADAS) +
           f", S/ {config.STAKE_SIMULADO} c/u)", bloque(filas, "Todas las sugerencias"),
           bloque([r for r in filas if r["tipo"] == "principal"], "Principales"),
           bloque([r for r in filas if r["tipo"] == "alternativa"], "Alternativas"),
           bloque([r for r in filas if r["valor"] == "si"], "Cuota sobre la justa del modelo"), ""]
    for cod in ("1", "2", "O2.5", "U2.5"):
        lin.append(bloque([r for r in filas if r["mercado"] == cod], f"Mercado {cod}"))
    for a, b in ((1.25, 1.60), (1.60, 2.00), (2.00, 2.61)):
        lin.append(bloque([r for r in filas if a <= float(r["cuota"]) < b], f"Cuotas {a:.2f}–{min(b, 2.60):.2f}"))
    lin.append("")
    lin.append(bloque(base, "Línea base (sin filtro de datazos)"))
    lin.append("<i>Si las sugerencias no superan a la línea base, los datazos no agregan precisión. "
               "CLV positivo sostenido es la mejor señal de ventaja real; ROI con pocas apuestas es ruido.</i>")
    return "\n".join(lin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--telegram", action="store_true")
    args = ap.parse_args()
    filas, base = simular()
    os.makedirs("data", exist_ok=True)
    if filas:
        with open("data/backtest.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            w.writeheader()
            w.writerows(filas)
    txt = resumen(filas, base)
    print("\n" + txt.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))
    if args.telegram:
        import bot
        bot.enviar(txt)


if __name__ == "__main__":
    main()
