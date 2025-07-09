import socket
import time
import os
import logging
import json
import sys
from pyais import decode
from pyais.exceptions import UnknownMessageException, MissingMultipartMessageException # Importa anche questa eccezione
from pyais.messages import NMEAMessageAssembler # <--- NUOVA IMPORTAZIONE


# --- CONFIGURAZIONE LOGGING (resta come prima) ---
LOG_DIRECTORY = "/app/storage"
LOG_FILE_NAME = "ais_output.log"
LOG_FILE_PATH = os.path.join(LOG_DIRECTORY, LOG_FILE_NAME)

os.makedirs(LOG_DIRECTORY, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
# --- FINE CONFIGURAZIONE LOGGING ---


# Configurazione generale del socket
BUFFER_SIZE = 1024 

def read_and_parse_moxa_ais_stream_interactive():
    # Logica di input IP/Porta (resta come prima)
    moxa_ip = input("Inserisci l'indirizzo IP del Moxa (es. 192.168.1.100): ").strip()
    
    while True:
        try:
            moxa_port_str = input("Inserisci la porta TCP del Moxa (es. 10001): ").strip()
            moxa_port = int(moxa_port_str)
            if not (0 <= moxa_port <= 65535):
                raise ValueError(f"La porta {moxa_port_str} non è valida. Deve essere tra 0 e 65535.")
            break
        except ValueError as e:
            logger.error(f"Input non valido: {e}. Riprova.")
        except EOFError:
            logger.critical("EOFError: Impossibile leggere l'input. Il container non è interattivo.")
            logger.critical("Si prega di avviare il container in modalità interattiva (es. docker run -it o oc rsh) o di fornire IP/Porta tramite variabili d'ambiente.")
            return

    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)

        logger.info(f"Tentativo di connessione a {moxa_ip}:{moxa_port}...")
        sock.connect((moxa_ip, moxa_port))
        logger.info("Connessione stabilita con successo!")
        logger.info(f"In attesa dello stream AIS. I log verranno scritti in {LOG_FILE_PATH}")

        received_buffer = b""
        
        # --- NUOVA INIZIALIZZAZIONE DELL'ASSEMBLER ---
        # Assembler per messaggi AIS multi-part
        # Timeout predefinito dell'assembler è 1 secondo, puoi cambiarlo se necessario.
        ais_assembler = NMEAMessageAssembler()
        # --- FINE NUOVA INIZIALIZZAZIONE ---

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
                if cr_index == -1 and lf_index == -1:
                    delimiter_index = -1
                elif cr_index == -1:
                    delimiter_index = lf_index
                elif lf_index == -1:
                    delimiter_index = cr_index
                else:
                    delimiter_index = min(cr_index, lf_index)

                if delimiter_index != -1:
                    raw_nmea_message_bytes = received_buffer[:delimiter_index]
                    received_buffer = received_buffer[delimiter_index + 1:]

                    if raw_nmea_message_bytes.endswith(b'\r') and received_buffer.startswith(b'\n'):
                        received_buffer = received_buffer[1:]

                    if raw_nmea_message_bytes:
                        raw_nmea_message_str = raw_nmea_message_bytes.decode('ascii', errors='ignore').strip()
                        
                        if raw_nmea_message_str.startswith(('!', '$')):
                            logger.info(f"RAW NMEA: {raw_nmea_message_str}") # Logga il messaggio RAW

                            # --- MODIFICA QUI: USA L'ASSEMBLER ---
                            try:
                                # Aggiungi il frammento all'assembler
                                assembled_message = ais_assembler.assemble(raw_nmea_message_str)

                                if assembled_message: # assembled_message sarà non-None solo quando un messaggio completo è pronto
                                    try:
                                        # Decodifica il messaggio AIS completo
                                        decoded_ais_message = decode(assembled_message)

                                        if decoded_ais_message:
                                            logger.info("\n--- Messaggio AIS Decodificato ---")
                                            
                                            log_data = {
                                                "timestamp": time.time(),
                                                "raw_nmea": assembled_message, # Logga il messaggio completo assemblato
                                                "msg_type": decoded_ais_message.msg_type,
                                                "mmsi": getattr(decoded_ais_message, 'mmsi', 'N/A'),
                                                "decoded_fields": {}
                                            }

                                            # Logica di estrazione campi (resta come prima)
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
                                                log_data["decoded_fields"] = decoded_ais_message.to_dict()
                                                log_data["decoded_fields"].pop('msg_type', None)
                                                log_data["decoded_fields"].pop('mmsi', None)

                                            logger.info(f"DECODED AIS (JSON): {json.dumps(log_data)}")
                                            
                                        else:
                                            logger.warning(f"AVVISO: Nessun oggetto decodificato da pyais per messaggio completo: {assembled_message}")

                                    except UnknownMessageException as e:
                                        logger.warning(f"AVVISO: Messaggio NMEA assemblato ma non decodificabile come AIS: {assembled_message} - {e}")
                                    except MissingMultipartMessageException as e: # <--- CATTURA QUESTA ECCEZIONE QUI
                                        # Questo accade se l'assembler rilascia un messaggio non completo a causa di timeout interni
                                        logger.warning(f"AVVISO: Eccezione di frammentazione messaggio AIS: {e} - messaggio parziale: {assembled_message}")
                                    except Exception as e:
                                        logger.error(f"ERRORE durante la decodifica AIS del messaggio assemblato '{assembled_message}': {e}", exc_info=True)

                            except Exception as e: # Questo catch è per errori nell'assembler stesso o NMEA non valido
                                logger.error(f"ERRORE durante l'assemblaggio del messaggio NMEA '{raw_nmea_message_str}': {e}", exc_info=True)

                        else:
                            logger.debug(f"RAW non NMEA: {raw_nmea_message_str}")
                else:
                    break
            
            if len(received_buffer) > BUFFER_SIZE * 4:
                logger.warning(f"ATTENZIONE: Buffer dati in crescita ({len(received_buffer)} bytes) senza delimitatori. Svuotamento parziale.")
                try:
                    logger.warning(f"Contenuto parziale del buffer (inizio): {received_buffer[:100].decode('ascii', errors='replace')}...")
                except:
                    logger.warning(f"Contenuto parziale del buffer (inizio, binario): {received_buffer[:100]}...")
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