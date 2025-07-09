# keep_alive_counter.py
import time
import os

print("--- Container Keep-Alive Counter Started ---")
print("This script keeps the container running for interactive access.")
print("To interact with your main application, use 'oc rsh' and then run 'python moxa_ais_parser.py'")
print("------------------------------------------\n")

counter = 0
while True:
    print(f"Container active for {counter} seconds...")
    counter += 1
    time.sleep(1) # Attendi 1 secondo