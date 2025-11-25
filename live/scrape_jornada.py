"""scrape_jornada.py

Extrae todos los partidos de una Fase (categoria) y una Jornada concreta
y devuelve un JSON con la lista de partidos: local, visitante, id, marcador (si existe).

Uso:
  from live.scrape_jornada import scrape_jornada
  data = scrape_jornada(fase="Grupo A", jornada=1)

O desde CLI:
  python -m live.scrape_jornada "Grupo A" 1

Se asume la temporada configurada en `utils.web_scraping` (por ejemplo 2025/2026).
"""

import re
import json
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from utils.web_scraping import (
    init_driver,
    accept_cookies,
    get_current_base_url,
    SELECT_ID_TEMPORADA,
    SELECT_ID_FASE,
    SELECT_ID_JORNADA,
)
import utils.web_scraping as web_scraping


def scrape_jornada(fase: str, jornada: int, wait_seconds: int = 15):
    """Scrapea una fase y jornada y devuelve un dict listo para serializar a JSON.

    Args:
        fase: Texto de la fase/categoría tal y como aparece en el select (ej: 'Grupo A').
        jornada: Número de jornada (1-based).
        wait_seconds: Timeout para WebDriverWait.

    Returns:
        dict: {"fase": str, "jornada": int, "matches": [ {"id": str, "local": str, "visitante": str, "score": str|None} ] }
    """

    driver = init_driver()
    try:
        base = get_current_base_url()
        driver.get(base)
        accept_cookies(driver)
        print(f"ℹ️ Navegando a URL base: {base}")


        wait = WebDriverWait(driver, wait_seconds)

        # Seleccionar temporada según la configuración central
        sel_temp = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_TEMPORADA)))
        Select(sel_temp).select_by_visible_text(web_scraping.TEMPORADA_TXT)
        # Esperar a que la opción seleccionada se actualice (robusto)
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, f"#{SELECT_ID_TEMPORADA} option[selected]"), web_scraping.TEMPORADA_TXT))

        # Seleccionar fase
        sel_fase = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_FASE)))
        Select(sel_fase).select_by_visible_text(fase)
        wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, f"#{SELECT_ID_FASE} option[selected]"), fase))

        # Seleccionar jornada (re-buscar el select para evitar stale elements)
        sel_jor = wait.until(EC.presence_of_element_located((By.ID, SELECT_ID_JORNADA)))
        select_obj = Select(sel_jor)
        # Convertir jornada (1-based) a índice
        idx = int(jornada) - 1
        if idx < 0 or idx >= len(select_obj.options):
            raise IndexError(f"Jornada {jornada} fuera de rango (1..{len(select_obj.options)})")
        select_obj.select_by_index(idx)

        # Esperar a que la tabla de jornada esté presente
        wait.until(EC.presence_of_element_located((By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid")))

        table = driver.find_element(By.ID, "_ctl0_MainContentPlaceHolderMaster_jornadaDataGrid")
        rows = table.find_elements(By.TAG_NAME, "tr")[1:]

        matches = []
        for tr in rows:
            # Equipos
            try:
                eq = tr.find_elements(By.CSS_SELECTOR, "td:nth-child(1) a")
                local = eq[0].text.strip()
                visit = eq[1].text.strip()
            except Exception:
                # Saltar si no tiene el formato esperado
                continue

            # Resultado y link que contiene el id
            try:
                res = tr.find_element(By.CSS_SELECTOR, "td:nth-child(2) a")
                marcador = res.text.strip()
                href = res.get_attribute("href") or ""
                pid_m = re.search(r"p=(\d+)", href)
                pid = pid_m.group(1) if pid_m else None
            except Exception:
                marcador = None
                pid = None

            matches.append({
                "id": pid,
                "local": local,
                "visitante": visit,
                "score": marcador if marcador else None,
            })

        return {"fase": fase, "jornada": int(jornada), "matches": matches}

    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    import sys

    grupo = "Liga Regular \"B-B\""
    jornada = "7"
    out = scrape_jornada(grupo, jornada)
    print(json.dumps(out, ensure_ascii=False, indent=2))
