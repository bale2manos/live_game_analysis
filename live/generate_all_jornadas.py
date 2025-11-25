"""generate_all_jornadas.py

Scrapea todas las jornadas (1..30) para el grupo fijo 'Liga Regular "B-B"'
usando `scrape_jornada` y guarda un JSON consolidado en `data/`.

Uso:
  python live/generate_all_jornadas.py

Nota: este script lanzará Selenium repetidamente (uno por jornada). Asegúrate
de tener el webdriver y dependencias configuradas. La temporada tomada será
la configurada en `utils.web_scraping.TEMPORADA_TXT` (asegúrate que sea 2025/2026).
"""

import json
from pathlib import Path
import time
import traceback

from scrape_jornada import scrape_jornada


GROUP = 'Liga Regular "B-B"'
JORNADAS = range(1, 27)


def main():
    root = Path(__file__).resolve().parent.parent
    out_dir = root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / "matches_2025_2026_B-B_3FEB.json"

    all_data = {"group": GROUP, "season": "2025/2026", "jornadas": []}

    for j in JORNADAS:
        print(f"Scraping jornada {j}...")
        try:
            res = scrape_jornada(GROUP, j)
            all_data["jornadas"].append(res)
            # pequeño descanso para no sobrecargar la web
            time.sleep(0.5)
        except Exception as e:
            print(f"Error en jornada {j}: {e}")
            traceback.print_exc()
            # continuar con la siguiente jornada
            all_data["jornadas"].append({"fase": GROUP, "jornada": j, "matches": [], "error": str(e)})

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    print(f"Guardado JSON en: {out_file}")


if __name__ == "__main__":
    main()
