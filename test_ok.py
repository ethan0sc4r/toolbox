import socket
import time
import os
import logging # Importa il modulo logging
import json    # Potrebbe essere utile per loggare oggetti complessi come JSON
from pyais import decode

# --- CONFIGURAZIONE LOGGING ---
LOG_DIRECTORY = "/app/storage" # La cartella 'storage' creata nel Dockerfile
LOG_FILE_NAME = "ais_output.log" # Nome del file di log
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, LOG_FILE_NAME)

# Assicurati che la directory di log esista
os.makedirs(LOG_DIRECTORY, exist_ok=True)

# Configura il logger
logging.basicConfig(
    level=logging.INFO, # Logga messaggi di livello INFO e superiori
    format='%(asctime)s - %(levelname)s - %(message)s', # Formato del log
    handlers=[
        logging.FileHandler(LOG_FILE_PATH), # Scrive i log su file
        logging.StreamHandler() # E anche sulla console (stdout/stderr)
    ]
)
# Ottieni un logger specifico per il tuo script
logger = logging.getLogger(__name__)
# --- FINE CONFIGURAZIONE LOGGING ---


# Configurazione generale del socket
BUFFER_SIZE = 1024 # Dimensione del buffer per la ricezione dei dati

def read_and_parse_moxa_ais_stream_interactive():
    # --- QUESTA PARTE E' RIMASTA INALTERATA RISPETTO AL TUO CODICE CHE FUNZIONAVA ---
    # Richiedi l'indirizzo IP all'utente
    moxa_ip = input("Inserisci l'indirizzo IP del Moxa (es. 192.168.1.100): ").strip()
    
    # Richiedi la porta all'utente e convertila a int
    while True:
        try:
            moxa_port_str = input("Inserisci la porta TCP del Moxa (es. 10001): ").strip()
            moxa_port = int(moxa_port_str)
            if not (0 <= moxa_port <= 65535):
                raise ValueError(f"La porta {moxa_port_str} non è valida. Deve essere tra 0 e 65535.")
            break
        except ValueError as e:
            # Sostituito print con logger.error
            logger.error(f"Input non valido: {e}. Riprova.")
        except EOFError: # Aggiunto EOFError per gestire il caso di stdin chiuso
            logger.critical("EOFError: Impossibile leggere l'input. Il container non è interattivo.")
            logger.critical("Si prega di avviare il container in modalità interattiva (es. docker run -it o oc rsh) o di fornire IP/Porta tramite variabili d'ambiente.")
            return # Termina lo script se l'input interattivo non è possibile
    # --- FINE PARTE INALTERATA ---


    sock = None
    try:
        # Crea un socket TCP/IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5) # Timeout di 5 secondi per la connessione

        # Sostituito print con logger.info
        logger.info(f"Tentativo di connessione a {moxa_ip}:{moxa_port}...")
        sock.connect((moxa_ip, moxa_port))
        logger.info("Connessione stabilita con successo!")
        logger.info(f"In attesa dello stream AIS. I log verranno scritti in {LOG_FILE_PATH}")

        received_buffer = b""

        while True:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                logger.warning("Connessione chiusa dal Moxa.") # Sostituito print con logger.warning
                break

            received_buffer += data

            while b'\r' in received_buffer or b'\n' in received_buffer:
                cr_index = received_buffer.find(b'\r')
                lf_index = received_buffer.find(b'\n')

                delimiter_index = -1
                if cr_index != -1 and lf_index != -1:
                    delimiter_index = min(cr_index, lf_index)
                elif cr_index != -1:
                    delimiter_index = cr_index
                elif lf_index != -1:
                    delimiter_index = lf_index

                if delimiter_index != -1:
                    raw_nmea_message_bytes = received_buffer[:delimiter_index]
                    received_buffer = received_buffer[delimiter_index + 1:]

                    if raw_nmea_message_bytes.endswith(b'\r') and received_buffer.startswith(b'\n'):
                        received_buffer = received_buffer[1:]

                    if raw_nmea_message_bytes:
                        raw_nmea_message_str = raw_nmea_message_bytes.decode('ascii', errors='ignore').strip()
                        
                        if raw_nmea_message_str.startswith(('!', '$')):
                            try:
                                logger.info(f"RAW NMEA: {raw_nmea_message_str}") # Sostituito print con logger.info
                                
                                decoded_ais_message = decode(raw_nmea_message_str)

                                if decoded_ais_message:
                                    logger.info("\n--- Messaggio AIS Decodificato ---") # Sostituito print con logger.info
                                    
                                    # Preparazione per il logging in JSON
                                    log_data = {
                                        "timestamp": time.time(),
                                        "raw_nmea": raw_nmea_message_str,
                                        "msg_type": decoded_ais_message.msg_type,
                                        "mmsi": getattr(decoded_ais_message, 'mmsi', 'N/A'),
                                        "decoded_fields": {}
                                    }

                                    # Estrai i campi in modo strutturato per il log
                                    if decoded_ais_message.msg_type in [1, 2, 3]:
                                        log_data["decoded_fields"] = {
                                            "status": getattr(decoded_ais_message, 'status', 'N/A'),
                                            "lat": getattr(decoded_ais_message, 'lat', 'N/A'),
                                            "lon": getattr(decoded_ais_message, 'lon', 'N/A'),
                                            "speed": getattr(decoded_ais_message, 'speed', 'N/A'),
                                            "course": getattr(decoded_ais_message, 'course', 'N/A'),
                                            "heading": getattr(decoded_ais_message, 'heading', 'N/A')
                                        }
                                    elif decoded_ais_message.msg_type == 5:
                                        log_data["decoded_fields"] = {
                                            "shipname": getattr(decoded_ais_message, 'shipname', 'N/A'),
                                            "ship_type": getattr(decoded_ais_message, 'ship_type', 'N/A'),
                                            "callsign": getattr(decoded_ais_message, 'callsign', 'N/A'),
                                            "imo": getattr(decoded_ais_message, 'imo', 'N/A'),
                                            "dimensions": {
                                                "to_bow": getattr(decoded_ais_message, 'to_bow', 'N/A'),
                                                "to_stern": getattr(decoded_ais_message, 'to_stern', 'N/A'),
                                                "to_port": getattr(decoded_ais_message, 'to_port', 'N/A'),
                                                "to_starboard": getattr(decoded_ais_message, 'to_starboard', 'N/A')
                                            }
                                        }
                                    elif decoded_ais_message.msg_type == 18:
                                        log_data["decoded_fields"] = {
                                            "lat": getattr(decoded_ais_message, 'lat', 'N/A'),
                                            "lon": getattr(decoded_ais_message, 'lon', 'N/A'),
                                            "speed": getattr(decoded_ais_message, 'speed', 'N/A'),
                                            "course": getattr(decoded_ais_message, 'course', 'N/A'),
                                            "unit": getattr(decoded_ais_message, 'unit', 'N/A')
                                        }
                                    elif decoded_ais_message.msg_type == 24:
                                        log_data["decoded_fields"]["part_num"] = getattr(decoded_ais_message, 'part_num', 'N/A')
                                        if hasattr(decoded_ais_message, 'shipname'):
                                            log_data["decoded_fields"]["shipname"] = decoded_ais_message.shipname
                                        if hasattr(decoded_ais_message, 'ship_type'):
                                            log_data["decoded_fields"]["ship_type"] = decoded_ais_message.ship_type
                                        if hasattr(decoded_ais_message, 'callsign'):
                                            log_data["decoded_fields"]["callsign"] = decoded_ais_message.callsign
                                    else:
                                        # Uso robusto di to_dict() per tutti gli altri messaggi (pyais)
                                        log_data["decoded_fields"] = decoded_ais_message.to_dict()
                                        log_data["decoded_fields"].pop('msg_type', None)
                                        log_data["decoded_fields"].pop('mmsi', None)


                                    logger.info(f"DECODED AIS (JSON): {json.dumps(log_data)}") # Logga l'oggetto JSON
                                    
                                else:
                                    logger.warning(f"AVVISO: Nessun oggetto decodificato da pyais per: {raw_nmea_message_str}") # Sostituito print

                            except Exception as e: # Cattura tutte le eccezioni di decodifica
                                logger.error(f"ERRORE durante la decodifica AIS di '{raw_nmea_message_str}': {e}", exc_info=True) # Logga con traceback

                        else:
                            logger.debug(f"RAW non NMEA: {raw_nmea_message_str}") # Sostituito print, livello DEBUG
                else:
                    break
            
            if len(received_buffer) > BUFFER_SIZE * 4:
                logger.warning(f"ATTENZIONE: Buffer dati in crescita ({len(received_buffer)} bytes) senza delimitatori. Svuotamento parziale.") # Sostituito print
                try:
                    logger.warning(f"Contenuto parziale del buffer (inizio): {received_buffer[:100].decode('ascii', errors='replace')}...") # Sostituito print
                except:
                    logger.warning(f"Contenuto parziale del buffer (inizio, binario): {received_buffer[:100]}...") # Sostituito print
                received_buffer = b""

    except ConnectionRefusedError:
        logger.error(f"Errore: Connessione rifiutata da {moxa_ip}:{moxa_port}.") # Sostituito print
        logger.error(f"Assicurati che il Moxa sia acceso, l'IP e la porta siano corretti, e che il limite di connessioni non sia già stato raggiunto.") # Sostituito print
    except socket.timeout:
        logger.error(f"Errore: Timeout della connessione a {moxa_ip}:{moxa_port}. Il Moxa non ha risposto entro il tempo limite.") # Sostituito print
        logger.error(f"  Verifica la connettività di rete tra il tuo ambiente e il Moxa.") # Sostituito print
    except Exception as e:
        logger.critical(f"Si è verificato un errore critico inatteso: {e}", exc_info=True) # Sostituito print
    finally:
        if sock:
            sock.close()
            logger.info("Socket chiuso.") # Sostituito print

if __name__ == "__main__":
    read_and_parse_moxa_ais_stream_interactive()