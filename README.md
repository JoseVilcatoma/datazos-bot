# 🤖 Bot de DATAZOS (365Scores → Telegram)

Cada día a las **20:00 (hora de Lima)** manda a Telegram los datazos de los partidos de **mañana** de tus ligas, con un análisis y una sugerencia basada en cuotas de Bet365. Corre gratis en GitHub Actions.

```
datazos-bot/
├── config.py          ← ligas, horario y reglas (lo único que vas a tocar)
├── s365.py            ← cliente de 365Scores (reintentos + caché)
├── datazos.py         ← datazos, puntaje, modelo Poisson y sugerencia
├── bot.py             ← Telegram, comandos, CSV y resumen
├── backtest.py        ← prueba las reglas en temporadas pasadas (football-data + Pinnacle)
├── requirements.txt
├── data/              ← enviados.json, estado.json, sugerencias.csv, backtest.csv (se guardan solos)
└── .github/workflows/datazos.yml
```

---

## PASO 1 — Crear el bot de Telegram (uno NUEVO)

Usa un bot distinto al de picks: este bot lee tus comandos con `getUpdates`, y si dos programas leen el mismo token se "roban" los mensajes.

1. En Telegram abre **@BotFather** → escribe `/newbot` → ponle nombre (ej. `Datazos Jose`) y usuario (ej. `datazos_jose_bot`).
2. Copia el **token** que te da (algo como `7123456789:AAH...`). Ese es `TELEGRAM_TOKEN`.
3. Abre tu bot nuevo y mándale cualquier mensaje (ej. `hola`).
4. En el navegador abre esta dirección (cambia `TU_TOKEN`):
   ```
   https://api.telegram.org/botTU_TOKEN/getUpdates
   ```
5. Busca `"chat":{"id":123456789` → ese número es `TELEGRAM_CHAT_ID`.

> El bot solo obedece comandos que vengan de ese chat.

---

## PASO 2 — Crear el repositorio en GitHub

1. Entra a https://github.com/new
2. Nombre: `datazos-bot` · marca **Public** · **no** agregues README.
3. Clic en **Create repository**.

---

## PASO 3 — Subir los archivos

### 3a. Los archivos normales
1. En el repo vacío, clic en **uploading an existing file**.
2. Descomprime el zip en tu PC y **arrastra**: `config.py`, `s365.py`, `datazos.py`, `bot.py`, `backtest.py`, `requirements.txt`, `README.md`, `.gitignore` y la carpeta `data`.
3. Clic en **Commit changes**.

### 3b. La carpeta `.github` (no se sube al arrastrar)
1. En el repo: **Add file → Create new file**.
2. En el nombre escribe exactamente (las barras crean las carpetas):
   ```
   .github/workflows/datazos.yml
   ```
3. Abre `datazos.yml` del zip con el Bloc de notas, copia **todo** y pégalo.
4. **Commit changes**.

> Si `.gitignore` o `data` no aparecen al arrastrar (Windows a veces oculta archivos con punto), créalos igual con **Create new file**: `data/estado.json` con el contenido `{}` y `data/enviados.json` con `{}`.

---

## PASO 4 — Poner los secrets

1. En el repo: **Settings → Secrets and variables → Actions → New repository secret**.
2. Crea dos:

| Name | Secret |
|---|---|
| `TELEGRAM_TOKEN` | el token de BotFather |
| `TELEGRAM_CHAT_ID` | el número de tu chat |

---

## PASO 5 — Dar permiso de escritura a Actions

El bot hace commit de `data/` para recordar qué mandó.

1. **Settings → Actions → General**.
2. Abajo, en **Workflow permissions**, marca **Read and write permissions** → **Save**.

---

## PASO 6 — Probarlo con "Run workflow"

1. Pestaña **Actions** → si pide, clic en **I understand my workflows, go ahead and enable them**.
2. A la izquierda clic en **Datazos** → botón **Run workflow**.
3. En **modo** elige `manana` → **Run workflow**.
4. Espera 2–6 minutos (la primera vez baja todo; luego usa caché). Te deben llegar los mensajes.
5. Si algo falla: entra a la corrida → paso **Correr el bot** → ahí sale el error.

Modos del botón:
- `auto` → lo normal (lee comandos, califica sugerencias, y si ya son las 20:00 manda lo de mañana una sola vez).
- `manana` / `hoy` → manda ya (aunque ya se haya mandado).
- `resumen` → manda el resumen de aciertos.
- `backtest` → prueba las reglas en 3 temporadas pasadas y manda el resultado (tarda ~5–10 min).

Desde ahí corre solo cada 15 minutos.

---

## Comandos en Telegram

```
/datazos hoy
/datazos mañana
/resumen
/ayuda
```

⚠️ GitHub Actions no está prendido todo el tiempo: el bot lee tus comandos en su siguiente corrida, así que la respuesta puede tardar **hasta ~15–20 min** (GitHub a veces atrasa los cron).

---

## Modo prueba en tu PC (no envía nada)

```bash
pip install -r requirements.txt
python bot.py --probar 4828481
```

`4828481` es el id del partido (es el número que aparece al final de la URL del partido en 365scores.com; ese es Galatasaray vs Barcelona del 13/10). Imprime el mensaje, **todos** los datazos candidatos con su puntaje, las señales y los goles esperados.

---

## Cambiar ligas u horario

Abre `config.py` en GitHub (ícono del lápiz) y edita:

```python
LIGAS_ACTIVAS = [572, 573, 7685, 7, 11, 17, 25, 35, 102, 389, 583]
HORA_ENVIO_DIARIO = 20
MAX_PARTIDOS = 20
```

Para agregar una liga nueva, ponla primero en `LIGAS = {...}` con su nombre corto.

---

## Cómo decide

**Datazos.** Rachas (ganados, invicto, sin ganar, marcando, arco en cero, local/visita), tendencias "X de los últimos N" (más de 2.5, ambos marcan, gol en el 1T, córners >9.5, tarjetas >4.5), H2H (rachas, último triunfo con fecha, promedio de goles, mismo cruce de local) y tabla. Cada uno tiene puntaje según largo de la racha, qué tan extremo es el porcentaje y tamaño de la muestra; se mandan máximo 5 (uno por tipo).

Reglas: H2H mínimo 4 partidos; tendencias mínimo 6; los amistosos no cuentan; si el H2H empieza hace 5+ años lo dice ("con otros planteles"). Si 365Scores solo trae parte del historial, el bot dice "sin triunfos en los N cruces registrados desde AAAA" en vez de inventar la fecha del último triunfo.

**Modelo.** Le quita el margen a las cuotas de Bet365, busca los goles esperados que reproducen esas cuotas (1X2 + más/menos) y los mezcla 75/25 con la estadística (últimos 10, local/visita y H2H reciente). Con Poisson calcula 1X2, doble oportunidad, más/menos 1.5/2.5/3.5, ambos marcan y hándicap ±1.5.

**Sugerencia.** Solo si los datazos y el mercado (probabilidad sin margen ≥ 50%) apuntan al mismo lado, con cuota entre 1.25 y 2.60. ✅ solo si Bet365 paga más que la cuota justa. No sugiere marcadores exactos ni combinadas (365Scores no trae la cuota real de una combinada y el bot no inventa cuotas).

**Seguimiento.** Cada sugerencia se guarda en `data/sugerencias.csv`; cuando termina el partido se marca `acierto`/`fallo` con el marcador de 90'. `/resumen` compara aciertos vs probabilidad esperada y la ganancia simulada con S/ 10.

---

## Datos extra que usa

- **xG (goles esperados)**: sale de las stats de 365Scores de los últimos 8 partidos. Da datazos ("generó 2.36 xG por partido en sus últimos 8", "marcó 17 goles con 12.0 xG: rinde por encima de lo esperado") y entra al modelo (50% goles reales, 50% xG). En ligas sin xG (por ejemplo Liga 1) simplemente no se usa.
- **Bajas**: lesionados y suspendidos que reporta 365Scores, con sus goles de la temporada. Salen en una línea 🚑 aparte (no cuentan dentro de los 5 datazos). Si falta un goleador de 5+ goles, el análisis lo menciona.
- **Más historial**: además de los ~25 partidos recientes, el bot pide 3 páginas más hacia atrás (~18 partidos). También busca cruces H2H dentro de ese historial largo.

Se ajusta en `config.py`:
```python
PAGINAS_HISTORIAL_EXTRA = 3
USAR_XG = True
PESO_XG = 0.5
```

---

## Backtest (¿las reglas sirven de verdad?)

En GitHub: **Actions → Datazos → Run workflow → modo `backtest`**. En tu PC:
```bash
python backtest.py
```

Baja gratis los CSV de football-data.co.uk (Premier, LaLiga, Serie A, Bundesliga, Ligue 1, Primeira; temporadas en `BACKTEST_TEMPORADAS`) y, partido por partido y sin mirar el futuro, aplica las mismas reglas del bot con las cuotas de Bet365. Te dice:

- **Aciertos vs esperado y ROI** apostando S/ 10 a cada sugerencia.
- **CLV contra el cierre de Pinnacle**: si la cuota que tomas es mejor que la de cierre de Pinnacle (la casa más afinada). CLV positivo sostenido es la mejor señal de ventaja real.
- **Línea base**: lo mismo pero sin exigir datazos. Si las sugerencias no le ganan a la línea base, los datazos no agregan precisión.
- Desglose por mercado y por rango de cuota (sirve para ajustar `CUOTA_MAXIMA`, `CUOTA_MINIMA`, etc.).

Limitación: football-data solo cubre ligas (no Champions ni copas) y sus cuotas útiles son 1X2 y más/menos 2.5, así que el backtest prueba esos mercados y no usa xG ni bajas.

---

## Límites honestos

- Pinnacle en vivo: 365Scores solo muestra Bet365 para Perú y la API de Pinnacle pide cuenta, así que Pinnacle se usa solo en el backtest.
- La API de 365Scores es no oficial: si cambia, el bot deja de traer datos (verás errores en Actions).
- Como el modelo pesa 75% las cuotas, casi nunca habrá "valor" grande: es lo esperable si el mercado es eficiente. El `/resumen` es lo que dirá si las sugerencias sirven; con menos de ~50 resultados es mayormente suerte.
- Equipos de ligas distintas (ej. Champions): la parte estadística compara rivales de nivel diferente; por eso pesa solo 25%.
- GitHub desactiva los cron si el repo pasa 60 días sin actividad; los commits diarios del bot lo mantienen activo.
