import sys
from pathlib import Path
import traceback
import json
import tempfile
import os

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
from scrape_jornada import scrape_jornada
from aranjuez_scrapper import parse_csv_to_json  # <-- para el modo Aranjuez

st.set_page_config(
    page_title="🏀 Generador de Informe de Partido",
    page_icon="🏀",
    layout="wide",
)

# --- Detectar modo por query params ( ?aranjuez=1 o ?mode=aranjuez ) ---
try:
    query_params = st.query_params  # Streamlit nuevo
except Exception:
    query_params = st.experimental_get_query_params()

IS_ARANJUEZ = (
    "aranjuez" in query_params
    or query_params.get("mode", [""])[0].lower() == "aranjuez"
)

# --- Helper común para mostrar/recordar el PDF en la sesión ---
def render_pdf_and_store(pdf_path: Path):
    if not pdf_path:
        st.error("`presentation_pdf` devolvió `None` o ruta vacía.")
        return

    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        st.error("El PDF fue reportado pero no se encontró en el sistema de archivos.")
        return

    # Leer PDF a bytes y guardarlo en session_state
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    st.session_state.pdf_file_bytes = pdf_bytes
    st.session_state.pdf_file_name = pdf_path.name

    # Botón de descarga inmediato
    st.download_button(
        label="Descargar PDF",
        data=pdf_bytes,
        file_name=pdf_path.name,
        mime="application/pdf",
    )

    # Convertir PDF a imágenes para visor móvil
    images_bytes = []
    converter_error = None
    try:
        import fitz  # PyMuPDF
        from io import BytesIO

        doc = fitz.open(str(pdf_path))
        zoom = 2  # mejor resolución
        mat = fitz.Matrix(zoom, zoom)
        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img_bytes = pix.tobytes("png")
            images_bytes.append(img_bytes)
        doc.close()
    except Exception as e1:
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
        st.error(
            "No se pudo convertir el PDF a imágenes. "
            "Instala `PyMuPDF` o `pdf2image` con sus dependencias."
        )
        st.error(f"Errores: {converter_error[0]} | {converter_error[1]}")
        return

    if images_bytes:
        st.session_state.pdf_images = images_bytes
        st.session_state.page_idx = 0
    else:
        st.info("No hay páginas para mostrar.")


def safe_init_driver():
    try:
        driver = init_driver()
        return driver
    except Exception as e:
        st.error(f"Error inicializando el driver: {e}")
        return None


# =====================================================================
# MODO ARANJUEZ (CSV → pipeline completo → PDF)
# =====================================================================
if IS_ARANJUEZ:
    st.title("🏀 Informe Basket Aranjuez desde CSV")
    st.write(
        "Este modo genera el informe a partir de un CSV local "
        "(pipeline `parse_csv_to_json → normalize_game_data → analyze_game → presentation_pdf`)."
    )

    # Botón grande que revela el file_uploader
    if "show_csv_uploader" not in st.session_state:
        st.session_state.show_csv_uploader = False

    if st.button("📂 Subir CSV y generar informe", use_container_width=True):
        st.session_state.show_csv_uploader = True

    uploaded_file = None
    if st.session_state.show_csv_uploader:
        uploaded_file = st.file_uploader(
            "Selecciona el archivo CSV del partido",
            type=["csv"],
            key="aranjuez_csv",
        )

    if uploaded_file is not None:
        # Guardar temporalmente el CSV para reutilizar la lógica del main_aranjuez
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded_file.getbuffer())
            tmp_path = tmp.name

        try:
            st.info(f"1️⃣ Leyendo datos del CSV…")
            try:
                # Pasar el nombre original del archivo subido para que
                # el parser pueda extraer correctamente los nombres de equipo
                raw_data = parse_csv_to_json(tmp_path, original_filename=uploaded_file.name)
            except Exception as e:
                st.error(f"Error crítico leyendo el CSV: {e}")
                raw_data = None

            if not raw_data:
                st.error(
                    "El scrapper devolvió datos vacíos. "
                    "Revisa la codificación o el formato del CSV."
                )
            else:
                st.info("2️⃣ Normalizando datos…")
                try:
                    norm_data = normalize_game_data(raw_data)
                except Exception as e:
                    st.error(f"Error en normalización: {e}")
                    norm_data = None

                if norm_data is not None:
                    st.info("3️⃣ Ejecutando motor estadístico…")
                    try:
                        analysis = analyze_game(norm_data)
                    except Exception as e:
                        st.error(f"Error en el motor de estadísticas: {e}")
                        analysis = None

                    if analysis is not None:

                        # PDF
                        st.subheader("📄 Informe en PDF")
                        try:
                            pdf_path = presentation_pdf(analysis)
                            if pdf_path:
                                render_pdf_and_store(pdf_path)
                                st.success("✅ PDF generado correctamente.")
                            else:
                                st.error(
                                    "`presentation_pdf` devolvió `None` o ruta vacía."
                                )
                        except Exception as e:
                            st.error(f"❌ Error generando el PDF: {e}")
        finally:
            # Borrar el temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

# =====================================================================
# MODO LIVE (jornadas + scraping) – lo que ya tenías
# =====================================================================
else:
    st.title("🏀 LIVE 3 FEB")
    st.write("Introduce el ID del partido y genera el informe que ahora mismo genera `live/main.py`.")

    # Fijar grupo
    GROUP_NAME = 'Liga Regular "B-B"'
    st.markdown(f"**Grupo fijado:** {GROUP_NAME}")

    # Usar lista estática de jornadas (1..30) en lugar de obtenerlas desde la web
    jornadas = list(range(1, 31))
    selected_jornada = st.selectbox(
        "Selecciona jornada:", jornadas, index=6, key="selected_jornada"
    )

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
                            st.info(
                                f"Jornada {selected_jornada} no encontrada en la base local. "
                                "Se realizará scraping."
                            )
                    except Exception as e:
                        st.error(f"Error leyendo la base local: {e}")
                else:
                    st.info(
                        "Base local no encontrada — se realizará scraping como fallback."
                    )

                # Fallback: si no hay matches en la base, hacemos scraping puntual
                if not matches:
                    res = scrape_jornada(GROUP_NAME, int(selected_jornada))
                    matches = res.get("matches", [])

                options = [
                    f"{m.get('local')} vs {m.get('visitante')} (id: {m.get('id') or '?'})"
                    for m in matches
                ]

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
        selected_display = st.selectbox(
            "Partido:", opts, index=idx, key="selected_match"
        )
        st.session_state.selected_match_idx = opts.index(selected_display)
    else:
        selected_display = None

    col1, col2 = st.columns([3, 1])

    with col1:
        run = st.button("Generar informe")

    with col2:
        # Mostrar botón de descarga persistente si ya hay un PDF generado
        if "pdf_file_bytes" in st.session_state and "pdf_file_name" in st.session_state:
            st.download_button(
                label="Descargar PDF",
                data=st.session_state.pdf_file_bytes,
                file_name=st.session_state.pdf_file_name,
                mime="application/pdf",
                key="top_download",
            )

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
            st.warning(
                "Por favor, selecciona un partido válido o introduce un ID de partido manualmente."
            )
        else:
            match_id = str(pid)
            status = st.empty()
            status.info(f"🔄 Iniciando scrape para partido {match_id}...")

            driver = safe_init_driver()
            data = None
            if driver is None:
                status.error(
                    "No se pudo inicializar el driver. Revisa la configuración del webdriver."
                )
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

                    # Generar PDF y mostrarlo
                    try:
                        with st.spinner("Generando PDF..."):
                            pdf_path = presentation_pdf(analysis)

                        if not pdf_path:
                            st.error(
                                "`presentation_pdf` devolvió `None` o ruta vacía."
                            )
                        else:
                            render_pdf_and_store(pdf_path)
                    except Exception as e:
                        st.error(f"Error generando o mostrando el PDF: {e}")
                        st.error(traceback.format_exc())

                except Exception as e:
                    st.error(f"Error en la pipeline de análisis: {e}")
                    st.error(traceback.format_exc())


# =====================================================================
# VISOR DE PDF (común a ambos modos)
# =====================================================================
if "pdf_images" in st.session_state:
    imgs = st.session_state.pdf_images
    total_pages = len(imgs)
    if "page_idx" not in st.session_state:
        st.session_state.page_idx = 0

    nav_col1, nav_col2, nav_col3 = st.columns([1, 6, 1])
    with nav_col1:
        if st.button("◀️ Anterior", key="prev_btn"):
            st.session_state.page_idx = max(0, st.session_state.page_idx - 1)
    with nav_col3:
        if st.button("Siguiente ▶️", key="next_btn"):
            st.session_state.page_idx = min(
                total_pages - 1, st.session_state.page_idx + 1
            )

    idx = st.session_state.page_idx
    st.markdown(f"**Página {idx+1} / {total_pages}**")
    st.image(imgs[idx], use_container_width=True)

    new_idx = st.slider(
        "Ir a página", 1, total_pages, idx + 1, key="page_slider"
    )
    if new_idx - 1 != idx:
        st.session_state.page_idx = new_idx - 1

st.markdown("---")
st.header("Notas")
st.write("- Modo LIVE: requiere webdriver funcional para `init_driver`.")
st.write(
    "- Modo Aranjuez: entra con `?aranjuez=1` en la URL y sube el CSV del partido."
)
st.write(
    "- Si el driver no arranca en tu entorno, ejecuta el script `live/main.py` dentro de la carpeta `live` para comprobar errores locales."
)
