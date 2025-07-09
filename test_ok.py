import socket
import time
import os
import logging # Importa il modulo logging
import json    # Potrebbe essere utile per loggare oggetti complessi come JSON
from pyais import decode

# --- CONFIGURAZIONE LOGGING ---
LOG_DIRECTORY = "/app/storage" # La cartella 'storage' creata nel Dockerfile
LOG_FILE_NAME = "ais_output.log" # Ho cambiato il nome del file per distinguere questo log specifico
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
    # Leggi l'indirizzo IP dalle variabili d'ambiente
    # Se MOXA_IP non è impostato, usa un valore predefinito o esci
    moxa_ip = os.getenv("MOXA_IP", "192.168.1.100") # Valore di default se non impostato
    
    # Leggi la porta dalle variabili d'ambiente
    moxa_port_str = os.getenv("MOXA_PORT", "10001") # Valore di default se non impostato
    
    try:
        moxa_port = int(moxa_port_str)
        if not (0 <= moxa_port <= 65535):
            raise ValueError(f"La porta {moxa_port_str} non è valida. Deve essere tra 0 e 65535.")
    except ValueError as e:
        # Usa logger.error al posto di print
        logger.error(f"Errore nella porta fornita via variabile d'ambiente: {e}")
        logger.error("Assicurati che le variabili d'ambiente MOXA_PORT siano numeri validi.")
        return # Termina lo script se la porta non è valida

    sock = None
    try:
        # Crea un socket TCP/IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5) # Timeout di 5 secondi per la connessione

        # Usa logger.info al posto di print
        logger.info(f"Tentativo di connessione a {moxa_ip}:{moxa_port} (ottenuto da variabili d'ambiente)...")
        sock.connect((moxa_ip, moxa_port))
        logger.info("Connessione stabilita con successo!")
        logger.info(f"In attesa dello stream AIS. I log verranno scritti in {LOG_FILE_PATH}")

        received_buffer = b""

        while True:
            data = sock.recv(BUFFER_SIZE)
            if not data:
                logger.warning("Connessione chiusa dal Moxa.") # Usa logger.warning
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
                                # Stampa il messaggio RAW (INFO)
                                logger.info(f"RAW NMEA: {raw_nmea_message_str}")
                                
                                decoded_ais_message = decode(raw_nmea_message_str)

                                if decoded_ais_message:
                                    # Logga i messaggi decodificati
                                    logger.info("\n--- Messaggio AIS Decodificato ---")
                                    logger.info(f"Tipo Messaggio (MsgID): {decoded_ais_message.msg_type}")
                                    logger.info(f"MMSI: {decoded_ais_message.mmsi}")
                                    
                                    # Formatta i dettagli specifici del messaggio per il log
                                    decoded_fields = {} # Dizionario per i campi decodificati
                                    
                                    if decoded_ais_message.msg_type in [1, 2, 3]:
                                        decoded_fields["Status Navigazione"] = getattr(decoded_ais_message, 'status', 'N/A')
                                        decoded_fields["Latitudine"] = getattr(decoded_ais_message, 'lat', 'N/A')
                                        decoded_fields["Longitudine"] = getattr(decoded_ais_message, 'lon', 'N/A')
                                        decoded_fields["Velocità (SOG)"] = f"{getattr(decoded_ais_message, 'speed', 'N/A')} nodi"
                                        decoded_fields["Rotta (COG)"] = f"{getattr(decoded_ais_message, 'course', 'N/A')} gradi"
                                        decoded_fields["Heading (True)"] = f"{getattr(decoded_ais_message, 'heading', 'N/A')} gradi"
                                    elif decoded_ais_message.msg_type == 5:
                                        decoded_fields["Nome Nave"] = getattr(decoded_ais_message, 'shipname', 'N/A')
                                        decoded_fields["Tipo Nave"] = getattr(decoded_ais_message, 'ship_type', 'N/A')
                                        decoded_fields["Call Sign"] = getattr(decoded_ais_message, 'callsign', 'N/A')
                                        decoded_fields["IMO"] = getattr(decoded_ais_message, 'imo', 'N/A')
                                        decoded_fields["Dimensioni - To Bow"] = f"{getattr(decoded_ais_message, 'to_bow', 'N/A')} m"
                                        decoded_fields["Dimensioni - To Stern"] = f"{getattr(decoded_ais_message, 'to_stern', 'N/A')} m"
                                        decoded_fields["Dimensioni - To Port"] = f"{getattr(decoded_ais_message, 'to_port', 'N/A')} m"
                                        decoded_fields["Dimensioni - To Starboard"] = f"{getattr(decoded_ais_message, 'to_starboard', 'N/A')} m"
                                    elif decoded_ais_message.msg_type == 18:
                                        decoded_fields["Latitudine"] = getattr(decoded_ais_message, 'lat', 'N/A')
                                        decoded_fields["Longitudine"] = getattr(decoded_ais_message, 'lon', 'N/A')
                                        decoded_fields["Velocità (SOG)"] = f"{getattr(decoded_ais_message, 'speed', 'N/A')} nodi"
                                        decoded_fields["Rotta (COG)"] = f"{getattr(decoded_ais_message, 'course', 'N/A')} gradi"
                                    elif decoded_ais_message.msg_type == 24:
                                        decoded_fields["Parte Messaggio 24"] = getattr(decoded_ais_message, 'part_num', 'N/A')
                                        if hasattr(decoded_ais_message, 'shipname'):
                                            decoded_fields["Nome Nave"] = decoded_ais_message.shipname
                                        if hasattr(decoded_ais_message, 'ship_type'):
                                            decoded_fields["Tipo Nave"] = decoded_ais_message.ship_type
                                        if hasattr(decoded_ais_message, 'callsign'):
                                            decoded_fields["Call Sign"] = decoded_ais_message.callsign
                                    else:
                                        # Per altri tipi di messaggi, stampa tutti i campi disponibili usando to_dict()
                                        # Questo metodo è robusto e disponibile per tutti gli oggetti pyais.
                                        decoded_fields = decoded_ais_message.to_dict()
                                        # Rimuovi i campi già stampati o non utili per una visualizzazione pulita se necessario
                                        decoded_fields.pop('msg_type', None)
                                        decoded_fields.pop('mmsi', None)


                                    # Logga i campi decodificati
                                    for key, value in decoded_fields.items():
                                        logger.info(f"  {key}: {value}")
                                    
                                    logger.info("-" * 30)
                                else:
                                    logger.warning(f"AVVISO: Nessun oggetto decodificato da pyais per: {raw_nmea_message_str}")

                            except Exception as e:
                                logger.error(f"ERRORE durante la decodifica AIS di '{raw_nmea_message_str}': {e}", exc_info=True) # Logga la traceback

                        else:
                            # Messaggi non NMEA (o NMEA non AIS), li logghiamo a livello DEBUG per non riempire troppo il log
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