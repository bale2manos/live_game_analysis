import sys
import os

# Módulos propios
from aranjuez_scrapper import parse_csv_to_json
from normalizer import normalize_game_data
from stats_engine import analyze_game
from presentation_text import generate_text_report, presentation_pdf

def main(csv_file):
    """
    Función principal que orquesta la lectura del CSV, normalización,
    análisis estadístico y generación de reportes.
    """
    
    # 0. Verificación de archivo
    if not os.path.exists(csv_file):
        print(f"Error: No se encuentra el archivo '{csv_file}' en el directorio actual.")
        return

    print(f"--- INICIO DEL PROCESO PARA: {csv_file} ---")

    # 1. EXTRACCIÓN (Sustituye a scrape_boxscore_live)
    # En lugar de usar Selenium, leemos el CSV localmente.
    print(f"1. Leyendo datos del CSV...")
    try:
        raw_data = parse_csv_to_json(csv_file)
    except Exception as e:
        print(f"Error crítico leyendo el CSV: {e}")
        return

    # Verificación rápida de que hay datos
    if not raw_data:
        print("Error: El scrapper devolvió datos vacíos. Revisa la codificación o el formato del CSV.")
        return
    
    # print(raw_data) # Descomentar si quieres ver el JSON crudo (debug)

    # 2. NORMALIZACIÓN
    # Convierte la estructura cruda en la estructura estandarizada (Local/Visitante con stats agregadas)
    print("2. Normalizando datos...")
    try:
        norm_data = normalize_game_data(raw_data)
    except Exception as e:
        print(f"Error en normalización: {e}")
        # A veces falla si el normalizer espera nombres de equipos específicos, 
        # pero con la lógica genérica debería pasar.
        return

    # 3. ANÁLISIS (Stats Engine)
    # Calcula posesiones, OER, DER, 4 Factors, etc.
    print("3. Ejecutando motor estadístico...")
    try:
        analysis = analyze_game(norm_data)
    except Exception as e:
        print(f"Error en el motor de estadísticas: {e}")
        return

    # 4. PRESENTACIÓN (Texto)
    print("\n" + "="*40)
    print("REPORTE DE TEXTO")
    print("="*40)
    try:
        print(generate_text_report(analysis))
    except Exception as e:
        print(f"No se pudo generar el reporte de texto: {e}")

    # 5. PRESENTACIÓN (PDF)
    print("\n" + "="*40)
    print("GENERACIÓN DE PDF")
    print("="*40)
    try:
        pdf_path = presentation_pdf(analysis)
        print(f"✅ ÉXITO: PDF generado correctamente: {pdf_path}")
    except Exception as e:
        print(f"❌ Error generando el PDF: {e}")

if __name__ == "__main__":
    # Nombre del archivo por defecto
    default_filename = "./data/stats-pizarro-vs-basket_aranjuez-23-11-2025.csv"
    
    # Permite pasar el nombre del archivo como argumento: python main_aranjuez.py otro_archivo.csv
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    else:
        filename = default_filename
        
    main(filename)