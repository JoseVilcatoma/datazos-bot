# -*- coding: utf-8 -*-
"""
CONFIGURACIÓN DEL BOT DE DATAZOS
Cambia aquí las ligas, horarios y reglas. No hace falta tocar los otros archivos.
"""

# ---------------------------------------------------------------
# 1) LIGAS (id de 365Scores -> nombre corto que sale en el mensaje)
# ---------------------------------------------------------------
LIGAS = {
    572: "Champions",
    573: "Europa League",
    7685: "Conference",
    7: "Premier",
    11: "LaLiga",
    17: "Serie A",
    25: "Bundesliga",
    35: "Ligue 1",
    102: "Libertadores",
    389: "Sudamericana",
    583: "Liga 1",
    113: "Brasileirão",
    73: "Primeira Liga",
}

# Ligas que el bot revisa. Borra o agrega ids de la lista de arriba.
LIGAS_ACTIVAS = [572, 573, 7685, 7, 11, 17, 25, 35, 102, 389, 583]

# Máximo de partidos por envío (para no llenar el chat). Se priorizan por liga
# en el orden de LIGAS_ACTIVAS y luego por hora.
MAX_PARTIDOS = 20

# ---------------------------------------------------------------
# 2) HORARIO
# ---------------------------------------------------------------
ZONA_HORARIA = "America/Lima"
HORA_ENVIO_DIARIO = 20          # 20 = 8 pm hora de Lima (manda los partidos de MAÑANA)

# ---------------------------------------------------------------
# 3) REGLAS DE CALIDAD DE LOS DATAZOS
# ---------------------------------------------------------------
MAX_DATAZOS_POR_PARTIDO = 5
MIN_PARTIDOS_H2H = 4            # muestra mínima para datazos H2H
MIN_PARTIDOS_TENDENCIA = 6      # muestra mínima para "X de los últimos N"
VENTANA_TENDENCIA = 10          # cuántos partidos recientes mirar para tendencias
PARTIDOS_CON_DETALLE = 8        # partidos recientes de los que se baja 1T, córners y tarjetas
ANIOS_H2H_ANTIGUO = 5           # si el H2H empieza hace más de esto, se avisa "con otros planteles"

PAGINAS_HISTORIAL_EXTRA = 3     # páginas extra de resultados antiguos (~6 partidos c/u)
USAR_XG = True                  # usar goles esperados (xG) en datazos y modelo si 365Scores los trae
PESO_XG = 0.5                   # en la parte estadística: 50% goles reales, 50% xG

# Competencias que NO cuentan para rachas (amistosos). 321 = "Partido Amistoso" en 365Scores.
COMPETICIONES_EXCLUIDAS = [321]
PALABRAS_EXCLUIDAS = ["amistoso", "friendly", "gamper", "trofeo"]

# ---------------------------------------------------------------
# 4) ANÁLISIS Y SUGERENCIA
# ---------------------------------------------------------------
BOOKMAKER_ID = 14               # 14 = Bet365 en 365Scores
PESO_MERCADO = 0.75             # 75% cuotas, 25% estadísticas
CUOTA_MAXIMA = 2.60             # nunca sugerir cuotas mayores
CUOTA_MINIMA = 1.25             # por debajo de esto no vale la pena
PROB_MINIMA_PRINCIPAL = 0.45    # la sugerencia principal debe tener al menos esta probabilidad
MEJORA_ALTERNATIVA = 0.07       # la "alternativa más segura" debe tener +7 puntos de probabilidad
STAKE_SIMULADO = 10             # S/ por sugerencia en /resumen

# ---------------------------------------------------------------
# 5) API 365SCORES (no oficial)
# ---------------------------------------------------------------
API_BASE = "https://webws.365scores.com/web"
API_PARAMS = {
    "appTypeId": 5,
    "langId": 14,
    "timezoneName": "America/Lima",
    "userCountryId": 112,
}
PAUSA_ENTRE_LLAMADAS = 0.4      # segundos entre llamadas para no saturar
REINTENTOS = 4
CARPETA_CACHE = "cache"
DIAS_BORRAR_CACHE = 21          # archivos de caché más viejos que esto se borran

# ---------------------------------------------------------------
# 6) BACKTEST (football-data.co.uk, gratis)
# ---------------------------------------------------------------
# Códigos de football-data -> nombre. Temporadas: "2425" = 2024/25.
BACKTEST_LIGAS = {"E0": "Premier", "SP1": "LaLiga", "I1": "Serie A",
                  "D1": "Bundesliga", "F1": "Ligue 1", "P1": "Primeira Liga"}
BACKTEST_TEMPORADAS = ["2324", "2425", "2526"]

# ---------------------------------------------------------------
# 7) ARCHIVOS DE ESTADO (se guardan en el repo con commit)
# ---------------------------------------------------------------
ARCHIVO_ENVIADOS = "data/enviados.json"
ARCHIVO_ESTADO = "data/estado.json"
ARCHIVO_SUGERENCIAS = "data/sugerencias.csv"
ARCHIVO_SEGUIMIENTO = "data/seguimiento.json"   # partidos enviados que esperan su resultado
HORAS_PARA_RESULTADO = 2                         # revisar el resultado 2 h después del inicio
