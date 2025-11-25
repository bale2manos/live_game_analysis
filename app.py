import sys
from pathlib import Path
import traceback

import streamlit as st

# Ensure the `live` folder is importable when running from repository root
ROOT = Path(__file__).parent
LIVE_PATH = ROOT / "live"
if str(LIVE_PATH) not in sys.path:
    sys.path.insert(0, str(LIVE_PATH))

from scraper_live import scrape_boxscore_live
from normalizer import normalize_game_data
from stats_engine import analyze_game
from presentation_text import generate_text_report, presentation_pdf
from utils.web_scraping import init_driver

st.set_page_config(page_title="🏀 Generador de Informe de Partido", page_icon="🏀", layout="wide")

st.title("🏀 LIVE 3 FEB")
st.write("Introduce el ID del partido y genera el informe que ahora mismo genera `live/main.py`.")

from scrape_jornada import scrape_jornada
import json

# Fijar grupo
GROUP_NAME = 'Liga Regular "B-B"'
st.markdown(f"**Grupo fijado:** {GROUP_NAME}")


# Usar lista estática de jornadas (1..30) en lugar de obtenerlas desde la web
jornadas = list(range(1, 31))
selected_jornada = st.selectbox("Selecciona jornada:", jornadas, index=6, key="selected_jornada")

# Inicializar variables de estado si no existen
if "match_options" not in st.session_state:
    st.session_state.match_options = []
    st.session_state.match_objs = []
    st.session_state.selected_match_idx = 0
    st.session_state.last_loaded_jornada = None

# Cargar automáticamente partidos cuando cambia la jornada seleccionada
try:
    jornada_changed = st.session_state.last_loaded_jornada != selected_jornada
except Exception:
    jornada_changed = True

if jornada_changed:
    # reset matches mientras cargamos
    st.session_state.match_options = []
    st.session_state.match_objs = []
    st.session_state.selected_match_idx = 0
    with st.spinner("Cargando partidos de la jornada..."):
        try:
            # Intentar cargar desde la base local
            db_path = ROOT / "data" / "matches_2025_2026_B-B_3FEB.json"
            matches = []
            if db_path.exists():
                try:
                    with open(db_path, "r", encoding="utf-8") as f:
                        db = json.load(f)
                    # buscar la jornada en db
                    found = None
                    for jrec in db.get("jornadas", []):
                        if int(jrec.get("jornada", 0)) == int(selected_jornada):
                            found = jrec
                            break
                    if found:
                        matches = found.get("matches", [])
                    else:
                        st.info(f"Jornada {selected_jornada} no encontrada en la base local. Se realizará scraping.")
                except Exception as e:
                    st.error(f"Error leyendo la base local: {e}")
            else:
                st.info("Base local no encontrada — se realizará scraping como fallback.")

            # Fallback: si no hay matches en la base, hacemos scraping puntual
            if not matches:
                res = scrape_jornada(GROUP_NAME, int(selected_jornada))
                matches = res.get("matches", [])

            options = [f"{m.get('local')} vs {m.get('visitante')} (id: {m.get('id') or '?'})" for m in matches]

            st.session_state.match_options = options
            st.session_state.match_objs = matches

            # Default: escoger el partido que contenga 'PINTOBASKET'
            default_idx = 0
            for i, opt in enumerate(options):
                if "PINTOBASKET" in opt.upper():
                    default_idx = i
                    break
            st.session_state.selected_match_idx = default_idx
            st.session_state.last_loaded_jornada = selected_jornada
        except Exception as e:
            st.error(f"Error cargando partidos: {e}")

# Mostrar selectbox de partidos solo después de cargar
selected_display = None
if st.session_state.match_options:
    opts = st.session_state.match_options
    idx = st.session_state.get("selected_match_idx", 0)
    selected_display = st.selectbox("Partido:", opts, index=idx, key="selected_match")
    st.session_state.selected_match_idx = opts.index(selected_display)
else:
    selected_display = None

col1, col2 = st.columns([3, 1])

with col1:
    run = st.button("Generar informe")

with col2:
    # Mostrar botón de descarga persistente si ya hay un PDF generado
    if "pdf_file_bytes" in st.session_state and "pdf_file_name" in st.session_state:
        st.download_button(label="Descargar PDF", data=st.session_state.pdf_file_bytes, file_name=st.session_state.pdf_file_name, mime="application/pdf", key="top_download")

def safe_init_driver():
    try:
        driver = init_driver()
        return driver
    except Exception as e:
        st.error(f"Error inicializando el driver: {e}")
        return None


if run:
    # Determinar el match_id a usar: prioridad al seleccionado en el desplegable
    pid = None
    if "match_options" in st.session_state and st.session_state.match_options:
        sel_idx = st.session_state.get("selected_match_idx", 0)
        try:
            pid = st.session_state.match_objs[sel_idx].get("id")
        except Exception:
            pid = None
    else:
        pid = None

    if not pid:
        st.warning("Por favor, selecciona un partido válido o introduce un ID de partido manualmente.")
    else:
        match_id = str(pid)
        status = st.empty()
        status.info(f"🔄 Iniciando scrape para partido {match_id}...")

        driver = safe_init_driver()
        data = None
        if driver is None:
            status.error("No se pudo inicializar el driver. Revisa la configuración del webdriver.")
        else:
            try:
                with st.spinner("Obteniendo boxscore en vivo..."):
                    data = scrape_boxscore_live(driver, match_id)
                status.success("Boxscore obtenido")
            except Exception as e:
                st.error(f"Error durante el scraping: {e}")
                st.error(traceback.format_exc())
            finally:
                try:
                    driver.quit()
                except Exception:
                    pass

        if data is not None:
            try:
                with st.spinner("Normalizando datos..."):
                    norm = normalize_game_data(data)
                status.info("Datos normalizados")

                with st.spinner("Analizando partido..."):
                    analysis = analyze_game(norm)
                status.info("Análisis completado")


                # Generar PDF y mostrarlo como imágenes para visualización móvil
                try:
                    with st.spinner("Generando PDF..."):
                        pdf_path = presentation_pdf(analysis)

                    if not pdf_path:
                        st.error("`presentation_pdf` devolvió `None` o ruta vacía.")
                    else:
                        pdf_path = Path(pdf_path)
                        if not pdf_path.exists():
                            st.error("El PDF fue reportado pero no se encontró en el sistema de archivos.")
                        else:
                            # PDF generado (mensaje oculto en UI)
                            # Leer pdf en bytes para ofrecer descarga y almacenarlo en session_state
                            with open(pdf_path, "rb") as f:
                                pdf_bytes = f.read()
                            # Guardar en session_state para que el botón de descarga persista
                            st.session_state.pdf_file_bytes = pdf_bytes
                            st.session_state.pdf_file_name = pdf_path.name
                            # Mostrar botón de descarga inmediato también
                            st.download_button(label="Descargar PDF", data=pdf_bytes, file_name=pdf_path.name, mime="application/pdf")

                            # Convertir PDF a imágenes y almacenarlas en session_state
                            # Intentar convertir usando PyMuPDF (fitz), si no está, intentar pdf2image
                            images_bytes = []
                            converter_error = None
                            try:
                                import fitz  # PyMuPDF
                                from io import BytesIO

                                doc = fitz.open(str(pdf_path))
                                zoom = 2  # mejora la resolución para pantallas móviles
                                mat = fitz.Matrix(zoom, zoom)
                                for page in doc:
                                    pix = page.get_pixmap(matrix=mat, alpha=False)
                                    img_bytes = pix.tobytes("png")
                                    images_bytes.append(img_bytes)
                                doc.close()
                            except Exception as e1:
                                # fall back to pdf2image if available
                                try:
                                    from pdf2image import convert_from_path
                                    from io import BytesIO

                                    pil_images = convert_from_path(str(pdf_path), dpi=200)
                                    for im in pil_images:
                                        buf = BytesIO()
                                        im.save(buf, format="PNG")
                                        images_bytes.append(buf.getvalue())
                                except Exception as e2:
                                    converter_error = (e1, e2)

                            if converter_error and not images_bytes:
                                st.error("No se pudo convertir el PDF a imágenes. Instala `PyMuPDF` o `pdf2image` con sus dependencias.")
                                st.error(f"Errores: {converter_error[0]} | {converter_error[1]}")
                            elif images_bytes:
                                # Almacenar en session_state para navegación (siempre actualizar)
                                st.session_state.pdf_images = images_bytes
                                st.session_state.page_idx = 0
                            else:
                                st.info("No hay páginas para mostrar.")
                except Exception as e:
                    st.error(f"Error generando o mostrando el PDF: {e}")
                    st.error(traceback.format_exc())

            except Exception as e:
                st.error(f"Error en la pipeline de análisis: {e}")
                st.error(traceback.format_exc())

        # status.info("Proceso finalizado")  # Mensaje final eliminado por petición del usuario

# Si ya hay imágenes en session_state, mostrar el visor fuera del flujo de generación
if "pdf_images" in st.session_state:
    imgs = st.session_state.pdf_images
    total_pages = len(imgs)
    if "page_idx" not in st.session_state:
        st.session_state.page_idx = 0

    # Nota: el botón de descarga persistente está en la cabecera junto a "Generar informe"

    # Controles: prev / next grandes para móvil (siempre mostrar el visor)
    nav_col1, nav_col2, nav_col3 = st.columns([1, 6, 1])
    with nav_col1:
        if st.button("◀️ Anterior", key="prev_btn"):
            st.session_state.page_idx = max(0, st.session_state.page_idx - 1)
    with nav_col3:
        if st.button("Siguiente ▶️", key="next_btn"):
            st.session_state.page_idx = min(total_pages - 1, st.session_state.page_idx + 1)

    idx = st.session_state.page_idx
    st.markdown(f"**Página {idx+1} / {total_pages}**")
    st.image(imgs[idx], use_container_width=True)

    new_idx = st.slider("Ir a página", 1, total_pages, idx + 1, key="page_slider")
    if new_idx - 1 != idx:
        st.session_state.page_idx = new_idx - 1

st.markdown("---")
st.header("Notas")
st.write("- Asegúrate de tener el webdriver y las dependencias necesarias para `init_driver`.")
st.write("- Si el driver no arranca en tu entorno, ejecuta el script `live/main.py` dentro de la carpeta `live` para comprobar errores locales.")
