import csv
import json
import re
import os
import sys
import unicodedata

def normalize_name(text):
    """
    Elimina tildes y caracteres especiales para estandarizar los nombres.
    Ejemplo: 'Raúl' -> 'Raul', 'Marín' -> 'Marin'
    """
    if not text:
        return "Unknown"
    
    # Normaliza a forma NFKD (separa letras de tildes)
    nfkd_form = unicodedata.normalize('NFKD', text)
    # Filtra caracteres que no son espaciado (las tildes sueltas) y codifica a ASCII
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])

def parse_time_to_minutes(time_str):
    """
    Convierte 'MM:SS' a minutos en formato float.
    """
    if not time_str or ":" not in time_str:
        return 0.0
    try:
        parts = time_str.split(':')
        minutes = int(parts[0])
        seconds = int(parts[1])
        return minutes + (seconds / 60.0)
    except ValueError:
        return 0.0

def safe_int(value):
    """Convierte string a int de forma segura, devolviendo 0 si falla."""
    if not value:
        return 0
    try:
        return int(value)
    except ValueError:
        return 0

def get_dorsal_from_row(row):
    """
    Intenta obtener el dorsal buscando variantes comunes de la columna Nº.
    """
    # Intentamos las variantes más comunes del símbolo
    val = row.get('Nº')      # Símbolo masculino ordinal (común en español)
    if val is None:
        val = row.get('N°')  # Símbolo de grado
    if val is None:
        val = row.get('No')  # Texto simple
    if val is None:
        val = row.get('#')   # Almohadilla
        
    return safe_int(val)

def map_row_to_player_stats(row):
    """
    Mapea una fila del CSV a la estructura de diccionario de jugador.
    """
    
    # Limpieza del nombre
    raw_name = row.get('Jugador', 'Unknown')
    clean_name = normalize_name(raw_name)

    return {
        "name": clean_name,
        "dorsal": get_dorsal_from_row(row),  # <--- Usamos la función robusta
        "min": parse_time_to_minutes(row.get('MIN', '00:00')),
        
        # Datos directos necesarios para el motor
        "pts": safe_int(row.get('PTS')),
        "blk": safe_int(row.get('BLK')),
        "val": safe_int(row.get('PIR')),

        # Tiros de 2
        "t2c": safe_int(row.get('2PM')),
        "t2i": safe_int(row.get('2PA')),
        
        # Tiros de 3
        "t3c": safe_int(row.get('3PM')),
        "t3i": safe_int(row.get('3PA')),
        
        # Tiros Libres
        "tlc": safe_int(row.get('FTM')),
        "tli": safe_int(row.get('FTA')),
        
        # Rebotes
        "orb": safe_int(row.get('OREB')),
        "drb": safe_int(row.get('DREB')),
        
        # Manejo
        "ast": safe_int(row.get('AST')),
        "stl": safe_int(row.get('STL')),
        "to":  safe_int(row.get('TOV')),
        
        # Faltas
        "pf": safe_int(row.get('PF')),
        "fd": safe_int(row.get('PFD'))
    }

def extract_game_info_from_filename(filename, original_filename=None):
    """
    Extrae nombres de equipos y fecha del nombre del archivo.
    """
    # Prefer the original filename (as uploaded) when available, because
    # Streamlit/file-uploaders often save files to a temp name.
    if original_filename:
        base = os.path.basename(original_filename)
    else:
        base = os.path.basename(filename)
    name_no_ext = os.path.splitext(base)[0]
    # Aceptar separadores '-' o '_' y prefijo 'stats-' o 'stats_'
    # Ejemplos válidos:
    #  stats-pizarro-vs-basket_aranjuez-23-11-2025.csv
    #  stats_pizarro_vs_basket_aranjuez_23_11_2025.csv
    pattern = r'^(?:stats[-_])(.+?)[-_]vs[-_](.+?)[-_](\d{1,2}[-_]\d{1,2}[-_]\d{2,4})$'
    match = re.search(pattern, name_no_ext, flags=re.IGNORECASE)

    if match:
        # Reemplazar guiones/underscores por espacios y normalizar capitalización
        local_raw = match.group(1).replace('_', ' ').replace('-', ' ').strip().title()
        visitor_raw = match.group(2).replace('_', ' ').replace('-', ' ').strip().title()
        # Estandarizar separador de fecha a '-'
        date_raw = match.group(3).replace('_', '-')
        return normalize_name(local_raw), normalize_name(visitor_raw), date_raw
    else:
        return "Local Team", "Visitor Team", "Unknown Date"

def parse_csv_to_json(csv_filepath, original_filename: str = None):
    print(f"Leyendo archivo CSV: {csv_filepath} (original name: {original_filename})")
    local_team_name, visitor_team_name, game_date = extract_game_info_from_filename(
        csv_filepath, original_filename=original_filename
    )
    
    local_players = []
    visitor_players = [] 
    
    local_score = 0
    visitor_score = 0
    
    found_first_total = False
    
    try:
        # VOLVEMOS A UTF-8-SIG para leer correctamente el símbolo Nº y las tildes originales
        with open(csv_filepath, mode='r', encoding='utf-8-sig') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Debug: imprimir las columnas detectadas para asegurar que Nº está ahí
            # print(f"Columnas detectadas: {reader.fieldnames}") 

            for row in reader:
                raw_name_check = row.get('Jugador', '').strip()
                
                if not raw_name_check or set(raw_name_check) == {'-'}:
                    continue
                
                if raw_name_check.lower() == 'total':
                    score = safe_int(row.get('PTS'))
                    if not found_first_total:
                        local_score = score
                        found_first_total = True
                    else:
                        visitor_score = score
                        # Sólo añadir 'Team Total' si no hay jugadores individuales
                        if not visitor_players:
                            dummy = map_row_to_player_stats(row)
                            dummy['name'] = "Team Total"
                            dummy['dorsal'] = 0
                            visitor_players.append(dummy)
                    continue
                # Si aún no hemos alcanzado la fila 'Total' del primer equipo,
                # los siguientes rows pertenecen al equipo local; en caso
                # contrario pertenecen al visitante.
                if not found_first_total:
                    local_players.append(map_row_to_player_stats(row))
                else:
                    visitor_players.append(map_row_to_player_stats(row))
                    
    except UnicodeDecodeError:
        print("Error: El archivo no parece ser UTF-8 válido.")
        return {}
    except Exception as e:
        print(f"Error general: {e}")
        return {}

    # Forzar que "Basket Aranjuez" sea siempre el equipo local
    def _is_basket_aranjuez(name: str) -> bool:
        if not name:
            return False
        s = name.lower()
        # Aceptar variantes que contengan ambas palabras o solo 'aranjuez'
        return ("basket" in s and "aranjuez" in s) or (s.strip() == "aranjuez")

    if _is_basket_aranjuez(visitor_team_name) and not _is_basket_aranjuez(local_team_name):
        # Intercambiar nombres, listas de jugadores y puntuaciones
        local_team_name, visitor_team_name = visitor_team_name, local_team_name
        local_players, visitor_players = visitor_players, local_players
        local_score, visitor_score = visitor_score, local_score

    game_data = {
        "game_id": f"{local_team_name} vs {visitor_team_name} - {game_date}",
        "status": "FINAL",
        "local": {
            "team": local_team_name,
            "score": local_score,
            "players": local_players
        },
        "visitor": {
            "team": visitor_team_name,
            "score": visitor_score,
            "players": visitor_players
        }
    }
    
    return game_data

if __name__ == "__main__":
    filename = "./data/stats-pizarro-vs-basket_aranjuez-23-11-2025.csv"
    if len(sys.argv) > 1:
        filename = sys.argv[1]

    if os.path.exists(filename):
        print(json.dumps(parse_csv_to_json(filename), indent=2, ensure_ascii=False))
    else:
        print(f"No se encuentra el archivo {filename}")