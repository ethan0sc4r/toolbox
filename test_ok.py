import socket
import time
import os
import logging # Importa il modulo logging
import json    # Potrebbe essere utile per loggare oggetti complessi come JSON
from pyais import decode

# --- CONFIGURAZIONE LOGGING ---
LOG_DIRECTORY = "/app/storage" # La cartella 'storage' creata nel Dockerfile
LOG_FILE_NAME = "ais_decoded.log"
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
BUFFER_SIZE = 1024 

def read_and_parse_moxa_ais_stream_interactive():
    # Leggi l'indirizzo IP dalle variabili d'ambiente
    moxa_ip = os.getenv("MOXA_IP", "192.168.1.100") 
    
    # Leggi la porta dalle variabili d'ambiente
    moxa_port_str = os.getenv("MOXA_PORT", "10001") 
    
    try:
        moxa_port = int(moxa_port_str)
        if not (0 <= moxa_port <= 65535):
            raise ValueError(f"La porta {moxa_port_str} non è valida. Deve essere tra 0 e 65535.")
    except ValueError as e:
        logger.error(f"Errore nella porta fornita via variabile d'ambiente: {e}")
        logger.error("Assicurati che le variabili d'ambiente MOXA_PORT siano numeri validi.")
        return 

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5) 

        logger.info(f"Tentativo di connessione a {moxa_ip}:{moxa_port} (ottenuto da variabili d'ambiente)...")
        sock.connect((moxa_ip, moxa_port))
        logger.info("Connessione stabilita con successo!")
        logger.info(f"In attesa dello stream AIS. I log verranno scritti in {LOG_FILE_PATH}")

        received_buffer = b""

        while True:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                logger.warning("Connessione chiusa dal Moxa.")
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
                                # Stampa il messaggio RAW sulla console (INFO)
                                logger.info(f"RAW NMEA: {raw_nmea_message_str}")
                                
                                decoded_ais_message = decode(raw_nmea_message_str)

                                if decoded_ais_message:
                                    logger.info("--- Messaggio AIS Decodificato ---")
                                    
                                    # Formatta i dati decodificati per il log
                                    log_data = {
                                        "timestamp": time.time(), # Aggiungi un timestamp per la decodifica
                                        "raw_nmea": raw_nmea_message_str,
                                        "msg_type": decoded_ais_message.msg_type,
                                        "mmsi": decoded_ais_message.mmsi,
                                        "decoded_fields": {}
                                    }

                                    # Estrai campi comuni per loggare
                                    if decoded_ais_message.msg_type in [1, 2, 3]: # Messaggi di posizione
                                        log_data["decoded_fields"] = {
                                            "status": getattr(decoded_ais_message, 'status', 'N/A'),
                                            "lat": getattr(decoded_ais_message, 'lat', 'N/A'),
                                            "lon": getattr(decoded_ais_message, 'lon', 'N/A'),
                                            "speed": getattr(decoded_ais_message, 'speed', 'N/A'),
                                            "course": getattr(decoded_ais_message, 'course', 'N/A'),
                                            "heading": getattr(decoded_ais_message, 'heading', 'N/A')
                                        }
                                    elif decoded_ais_message.msg_type == 5: # Dati nave statici
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
                                    # Puoi estendere questa logica per altri tipi di messaggi
                                    else:
                                        # Per tipi sconosciuti o meno comuni, logga tutti gli attributi pubblici
                                        for field in decoded_ais_message.__dataclass_fields__:
                                            attr_value = getattr(decoded_ais_message, field)
                                            if not field.startswith('_') and not callable(attr_value):
                                                log_data["decoded_fields"][field] = attr_value

                                    # Logga l'oggetto decodificato come stringa JSON per facile parsing futuro
                                    logger.info(f"DECODED AIS (JSON): {json.dumps(log_data)}")
                                    
                                else:
                                    logger.warning(f"AVVISO: Nessun oggetto decodificato da pyais per: {raw_nmea_message_str}")

                            except Exception as e:
                                logger.error(f"ERRORE durante la decodifica AIS di '{raw_nmea_message_str}': {e}", exc_info=True) # exc_info=True logga la traceback

                        else:
                            logger.debug(f"RAW non NMEA (saltato): {raw_nmea_message_str}") # Usiamo DEBUG per non inondare i log con non-AIS
                else:
                    break
            
            if len(received_buffer) > BUFFER_SIZE * 4:
                logger.warning(f"ATTENZIONE: Buffer dati in crescita ({len(received_buffer)} bytes) senza delimitatori. Svuotamento parziale.")
                received_buffer = b""

    except ConnectionRefusedError:
        logger.error(f"Errore: Connessione rifiutata da {moxa_ip}:{moxa_port}.")
        logger.error(f"Assicurati che il Moxa sia acceso, l'IP e la porta siano corretti, e che il limite di connessioni non sia già stato raggiunto.")
    except socket.timeout:
        logger.error(f"Errore: Timeout della connessione a {moxa_ip}:{moxa_port}. Il Moxa non ha risposto entro il tempo limite.")
        logger.error(f"  Verifica la connettività di rete tra il tuo ambiente e il Moxa.")
    except Exception as e:
        logger.critical(f"Si è verificato un errore critico inatteso: {e}", exc_info=True)
    finally:
        if sock:
            sock.close()
            logger.info("Socket chiuso.")

if __name__ == "__main__":
    read_and_parse_moxa_ais_stream_interactive()