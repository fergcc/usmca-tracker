# TMEC Intelligence Engine v1.0

Engine de inteligencia comercial para monitorear y analizar el T-MEC/USMCA/CUSMA.
Busca contenido en la web via SearchAPI.io y lo analiza con DeepSeek AI.

---

## Requisitos

- Python 3.12+
- pip
- API keys de:
  - [SearchAPI.io](https://www.searchapi.io/) (búsqueda web)
  - [DeepSeek](https://platform.deepseek.com/) (análisis AI)

---

## Instalación

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Copiar template de variables de entorno
cp .env.example .env

# 3. Editar .env con tus keys reales
#    nano .env   (o el editor de tu preferencia)
```

El archivo `.env` (NUNCA se commitea) debe contener:

```
SEARCH_API_KEY=tu_key_de_searchapi
DEEPSEEK_API_KEY=tu_key_de_deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

---

## Probar conectividad

```bash
python -c "
import os, sys
sys.path.insert(0, '.')
from pathlib import Path

# Cargar .env
env_path = Path('.env')
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, _, v = line.partition('=')
                os.environ[k.strip()] = v.strip().strip('\"')

from search_client import SearchClient
from deepseek_client import DeepSeekClient

# SearchAPI
try:
    c = SearchClient()
    r = c.search_web('USMCA test', num=2)
    print(f'SearchAPI: OK — {len(r)} resultados')
except Exception as e:
    print(f'SearchAPI: ERROR — {e}')

# DeepSeek
try:
    c = DeepSeekClient()
    r = c.chat([{'role':'user','content':'Di OK'}], max_tokens=5)
    print(f'DeepSeek:  OK — \"{r}\"')
except Exception as e:
    print(f'DeepSeek:  ERROR — {e}')
"
```

---

## Uso

### Pipeline completo (búsqueda + análisis AI)

```bash
python -m engine run --source /ruta/a/tus/items.jsonl --output /ruta/a/enriched.jsonl
```

### Solo búsqueda (sin análisis AI)

```bash
python -m engine search --source /ruta/a/tus/items.jsonl
```

### Solo análisis AI (sobre datos existentes, sin buscar)

```bash
python -m engine enrich --source /ruta/a/tus/items.jsonl --output /ruta/a/enriched.jsonl
```

### Preview sin modificar archivos

```bash
python -m engine dry-run --source /ruta/a/tus/items.jsonl
```

---

## Integración con cron / systemd

### Cron (cada 6 horas)

```cron
0 */6 * * * cd /opt/tmec-engine && python -m engine run --source /data/usmca/items.jsonl --output /data/usmca/items_enriched.jsonl >> /var/log/tmec-engine.log 2>&1
```

### systemd timer

Crear `/etc/systemd/system/tmec-engine.service`:

```ini
[Unit]
Description=TMEC Intelligence Engine

[Service]
Type=oneshot
WorkingDirectory=/opt/tmec-engine
EnvironmentFile=/opt/tmec-engine/.env
ExecStart=/usr/bin/python3 -m engine run --source /data/usmca/items.jsonl --output /data/usmca/items_enriched.jsonl
```

Crear `/etc/systemd/system/tmec-engine.timer`:

```ini
[Unit]
Description=TMEC Engine every 6 hours

[Timer]
OnCalendar=*-*-* 00/6:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Activar:

```bash
sudo systemctl enable tmec-engine.timer
sudo systemctl start tmec-engine.timer
```

---

## Estructura de datos

### items.jsonl (entrada)

JSONL con un objeto por línea:

```json
{"title": "...", "url": "...", "summary": "...", "source": "...", "published": "2026-07-17", "score": 5, "tags": ["!joint review", "@Greer"]}
```

### items_enriched.jsonl (salida)

Mismos campos + enriquecimiento AI:

```json
{"title": "...", "url": "...", "summary": "...", "score": 5, "tags": [...], "aiSummary": "Resumen en español generado por DeepSeek...", "sentiment": "negative", "impactScore": 8, "impactReason": "Este artículo señala tensiones en reglas de origen automotriz", "aiEntities": ["@Greer", "#automotive", "@Ebrard"]}
```

---

## Variables de entorno

| Variable | Descripción |
|---|---|
| `SEARCH_API_KEY` | API key de SearchAPI.io |
| `DEEPSEEK_API_KEY` | API key de DeepSeek |
| `DEEPSEEK_BASE_URL` | URL base de DeepSeek (default: `https://api.deepseek.com`) |

El vault central de Scientika está en `~/.secrets/scientika.env`. Carga las variables con:

```bash
set -a && source ~/.secrets/scientika.env && set +a
```

---

## Archivos

```
tmec-engine-v1.0/
├── .env.example          # Template — copiar a .env con keys reales
├── requirements.txt      # openai>=1.0.0, PyYAML>=6.0.1
├── config.yaml           # Queries, prompts, rate-limiting
├── engine.py             # CLI principal
├── search_client.py      # Wrapper HTTP de SearchAPI.io
├── deepseek_client.py    # Cliente DeepSeek (OpenAI-compatible)
├── analyzer.py           # Pipeline de análisis AI
├── enrich.py             # Lector/escritor JSONL + merge
└── README.md             # Este archivo
```
