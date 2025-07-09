import socket
import time
from pyais import decode
# Non abbiamo bisogno di importare Message esplicitamente da pyais per questo uso,
# ma non fa male se lo si volesse per type hints o controlli più specifici.

# Configurazione generale
BUFFER_SIZE = 1024 # Dimensione del buffer per la ricezione dei dati

def read_and_parse_moxa_ais_stream_interactive():
    # Richiedi l'indirizzo IP all'utente
    moxa_ip = input("Inserisci l'indirizzo IP del Moxa (es. 192.168.1.100): ").strip()
    
    # Richiedi la porta all'utente e convertila a int
    while True:
        try:
            moxa_port_str = input("Inserisci la porta TCP del Moxa (es. 10001): ").strip()
            moxa_port = int(moxa_port_str)
            if not (0 <= moxa_port <= 65535):
                raise ValueError("La porta deve essere tra 0 e 65535.")
            break
        except ValueError as e:
            print(f"Input non valido: {e}. Riprova.")

    sock = None # Inizializza il socket a None
    try:
        # Crea un socket TCP/IP
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Aggiungi un timeout di connessione
        sock.settimeout(5) # 5 secondi di timeout per la connessione

        # Connettiti al dispositivo Moxa
        print(f"Tentativo di connessione a {moxa_ip}:{moxa_port}...")
        sock.connect((moxa_ip, moxa_port))
        print("Connessione stabilita con successo!")
        print("In attesa dello stream AIS...")

        received_buffer = b"" # Buffer per accumulare i dati ricevuti

        while True:
            # Ricevi dati dal Moxa
            data = sock.recv(BUFFER_SIZE)
            if not data:
                print("Connessione chiusa dal Moxa.")
                break

            received_buffer += data

            # Processa i dati riga per riga, cercando i delimitatori (CR = 0x0D, LF = 0x0A)
            while b'\r' in received_buffer or b'\n' in received_buffer:
                # Trova il primo delimitatore
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
                    # Estrai la riga completa e pulisci il buffer
                    raw_nmea_message_bytes = received_buffer[:delimiter_index]
                    received_buffer = received_buffer[delimiter_index + 1:]

                    # Consuma il LF extra se il primo era CR
                    if raw_nmea_message_bytes.endswith(b'\r') and received_buffer.startswith(b'\n'):
                        received_buffer = received_buffer[1:] # Rimuovi il LF dal buffer

                    if raw_nmea_message_bytes: # Processa solo se la riga non è vuota
                        # Decodifica la riga grezza in stringa per il parsing AIS
                        raw_nmea_message_str = raw_nmea_message_bytes.decode('ascii', errors='ignore').strip()
                        
                        # I messaggi AIS NMEA iniziano con '!' o '$'
                        if raw_nmea_message_str.startswith(('!', '$')):
                            try:
                                # Stampa il messaggio RAW prima di tentare il parsing
                                print(f"RAW NMEA: {raw_nmea_message_str}")
                                
                                # Decodifica il messaggio AIS con pyais
                                decoded_ais_message = decode(raw_nmea_message_str)

                                if decoded_ais_message:
                                    print("\n--- Messaggio AIS Decodificato ---")
                                    # Stampa i dettagli del messaggio
                                    print(f"Tipo Messaggio (MsgID): {decoded_ais_message.msg_type}")
                                    print(f"MMSI: {decoded_ais_message.mmsi}")
                                    
                                    # Esempi di campi comuni per diversi tipi di messaggi
                                    if decoded_ais_message.msg_type in [1, 2, 3]: # Messaggi di posizione
                                        print(f"Status Navigazione: {getattr(decoded_ais_message, 'status', 'N/A')}")
                                        print(f"Latitudine: {getattr(decoded_ais_message, 'lat', 'N/A')}")
                                        print(f"Longitudine: {getattr(decoded_ais_message, 'lon', 'N/A')}")
                                        print(f"Velocità (SOG): {getattr(decoded_ais_message, 'speed', 'N/A')} nodi")
                                        print(f"Rotta (COG): {getattr(decoded_ais_message, 'course', 'N/A')} gradi")
                                        print(f"Heading (True): {getattr(decoded_ais_message, 'heading', 'N/A')} gradi")
                                    elif decoded_ais_message.msg_type == 5: # Dati nave statici e relativi al viaggio
                                        print(f"Nome Nave: {getattr(decoded_ais_message, 'shipname', 'N/A')}")
                                        print(f"Tipo Nave: {getattr(decoded_ais_message, 'ship_type', 'N/A')}")
                                        print(f"Call Sign: {getattr(decoded_ais_message, 'callsign', 'N/A')}")
                                        print(f"IMO: {getattr(decoded_ais_message, 'imo', 'N/A')}")
                                        print(f"Dimensioni - To Bow: {getattr(decoded_ais_message, 'to_bow', 'N/A')} m")
                                        print(f"Dimensioni - To Stern: {getattr(decoded_ais_message, 'to_stern', 'N/A')} m")
                                        print(f"Dimensioni - To Port: {getattr(decoded_ais_message, 'to_port', 'N/A')} m")
                                        print(f"Dimensioni - To Starboard: {getattr(decoded_ais_message, 'to_starboard', 'N/A')} m")
                                    elif decoded_ais_message.msg_type == 18: # Classe B CS Standard Posizione Report
                                        print(f"Latitudine: {getattr(decoded_ais_message, 'lat', 'N/A')}")
                                        print(f"Longitudine: {getattr(decoded_ais_message, 'lon', 'N/A')}")
                                        print(f"Velocità (SOG): {getattr(decoded_ais_message, 'speed', 'N/A')} nodi")
                                        print(f"Rotta (COG): {getattr(decoded_ais_message, 'course', 'N/A')} gradi")
                                        print(f"Unità (Class B): {getattr(decoded_ais_message, 'unit', 'N/A')}") # Typical for Msg 18
                                    elif decoded_ais_message.msg_type == 24: # Classe B Static Data Report
                                        # Messaggio 24 è spesso in due parti (0 e 1)
                                        print(f"Parte Messaggio 24: {getattr(decoded_ais_message, 'part_num', 'N/A')}")
                                        # Gli attributi dipendono dalla parte
                                        if hasattr(decoded_ais_message, 'shipname'):
                                            print(f"Nome Nave: {decoded_ais_message.shipname}")
                                        if hasattr(decoded_ais_message, 'ship_type'):
                                            print(f"Tipo Nave: {decoded_ais_message.ship_type}")
                                        if hasattr(decoded_ais_message, 'callsign'):
                                            print(f"Call Sign: {decoded_ais_message.callsign}")
                                    else:
                                        # Per altri tipi di messaggi, stampa tutti i campi disponibili
                                        print(f"Dettagli completi del messaggio (MsgID {decoded_ais_message.msg_type}):")
                                        # I messaggi pyais sono istanze di dataclasses, possiamo iterare i loro campi
                                        for field in decoded_ais_message.__dataclass_fields__:
                                            attr_value = getattr(decoded_ais_message, field)
                                            # Evita di stampare attributi "speciali" o metodi se non desiderato
                                            if not field.startswith('_') and not callable(attr_value):
                                                print(f"  {field}: {attr_value}")
                                    
                                    print("-" * 30) # Separatore per i messaggi decodificati
                                else:
                                    print(f"AVVISO: Nessun oggetto decodificato da pyais per: {raw_nmea_message_str}")

                            except Exception as e:
                                print(f"ERRORE durante la decodifica AIS di '{raw_nmea_message_str}': {e}")
                        else:
                            # Non un messaggio NMEA valido (non inizia con '!' o '$')
                            print(f"RAW non NMEA: {raw_nmea_message_str}")
                else:
                    break # Nessun delimitatore trovato, esci dal ciclo interno e attendi altri dati
            
            # Prevenire l'overflow del buffer
            if len(received_buffer) > BUFFER_SIZE * 4: # Se il buffer è troppo grande (es. 4KB)
                print(f"ATTENZIONE: Buffer dati in crescita ({len(received_buffer)} bytes) senza delimitatori. Svuotamento parziale.")
                try:
                    print(f"Contenuto parziale del buffer (inizio): {received_buffer[:100].decode('ascii', errors='replace')}...")
                except:
                    print(f"Contenuto parziale del buffer (inizio, binario): {received_buffer[:100]}...")
                received_buffer = b"" # Svuota il buffer

    except ConnectionRefusedError:
        print(f"Errore: Connessione rifiutata da {moxa_ip}:{moxa_port}.")
        print(f"Assicurati che il Moxa sia acceso, l'IP e la porta siano corretti, e che il limite di connessioni non sia già stato raggiunto.")
    except socket.timeout:
        print(f"Errore: Timeout della connessione a {moxa_ip}:{moxa_port}. Il Moxa non ha risposto entro il tempo limite.")
        print(f"  Verifica la connettività di rete tra il tuo ambiente e il Moxa.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
    finally:
        if sock:
            sock.close()
            print("Socket chiuso.")

if __name__ == "__main__":
    read_and_parse_moxa_ais_stream_interactive()