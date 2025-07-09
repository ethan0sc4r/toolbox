import socket
import time

# Configurazione del Moxa per i delimitatori (CR e LF) e dimensione del buffer
BUFFER_SIZE = 1024

def read_raw_moxa_stream_interactive():
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
        print("In attesa dello stream di dati grezzi dal Moxa...")

        received_buffer = b"" # Buffer per accumulare i dati ricevuti

        while True:
            # Ricevi dati dal Moxa
            data = sock.recv(BUFFER_SIZE)
            if not data:
                print("Connessione chiusa dal Moxa.")
                break

            received_buffer += data

            # Processa i dati riga per riga, cercando i delimitatori (CR = 0x0D, LF = 0x0A)
            # come configurato nel Moxa (Data Packing)
            while b'\r' in received_buffer or b'\n' in received_buffer:
                # Trova il primo delimitatore (CR o LF)
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
                    # Estrai la riga fino al delimitatore (incluso il delimitatore per una stampa fedele)
                    raw_line_bytes = received_buffer[:delimiter_index + 1]
                    received_buffer = received_buffer[delimiter_index + 1:]

                    # Se la riga era terminata da CR e il prossimo è LF, consuma anche LF
                    if raw_line_bytes.endswith(b'\r') and received_buffer.startswith(b'\n'):
                        raw_line_bytes += received_buffer[0:1] # Aggiungi LF alla riga corrente
                        received_buffer = received_buffer[1:] # Rimuovi LF dal buffer

                    try:
                        # Decodifica in stringa per la visualizzazione.
                        # Usa 'ascii' con errors='replace' per gestire caratteri non ASCII senza bloccare.
                        decoded_line = raw_line_bytes.decode('ascii', errors='replace')
                        print(f"RAW Moxa: {decoded_line.strip()}") # .strip() rimuove spazi bianchi, non i CRLF se già inclusi
                    except UnicodeDecodeError:
                        # Se ci sono dati non testuali che non possono essere decodificati
                        print(f"RAW Moxa (BINARIO): {raw_line_bytes}")
                else:
                    # Nessun delimitatore trovato nel buffer attuale, attendi altri dati
                    break # Esci dal ciclo interno e attendi un nuovo recv

            # Prevenire l'overflow del buffer se per qualche motivo i delimitatori non vengono trovati
            if len(received_buffer) > BUFFER_SIZE * 4:
                print(f"ATTENZIONE: Buffer dati grezzi in crescita ({len(received_buffer)} bytes) senza delimitatori. Svuotamento parziale.")
                try:
                    print(f"Contenuto parziale del buffer (inizio): {received_buffer[:100].decode('ascii', errors='replace')}...")
                except:
                    print(f"Contenuto parziale del buffer (inizio, binario): {received_buffer[:100]}...")
                received_buffer = b"" # Svuota il buffer

    except ConnectionRefusedError:
        print(f"Errore: Connessione rifiutata da {moxa_ip}:{moxa_port}.")
        print(f"Assicurati che il Moxa sia acceso, l'IP e la porta siano corretti, e che il limite di connessioni ({3}) non sia già stato raggiunto.")
    except socket.timeout:
        print(f"Errore: Timeout della connessione a {moxa_ip}:{moxa_port}. Il Moxa non ha risposto entro il tempo limite.")
        print(f"  Verifica la connettività di rete tra il tuo ambiente e il Moxa.")
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
    finally:
        # Chiudi il socket quando hai finito o in caso di errore
        if sock:
            sock.close()
            print("Socket chiuso.")

if __name__ == "__main__":
    read_raw_moxa_stream_interactive()