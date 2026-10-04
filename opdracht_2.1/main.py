import socket
import sys
import time
import subprocess

ALLOWED_PROGRAMS = ["notepad", "calc"]  # Voeg hier de toegestane programma's toe

HOST = ''   # Alle beschikbare interfaces
PORT = 8888 # Willekeurige poort (denk aan firewall bij Windows Systemen)

global_login_status = 'not_logged_in'  # Variabele om de login status bij te houden
global_username = ''
global_password = ''
last_started_program = None  # Variabele om het laatst gestarte programma bij te houden

def update_login_status(status: str) -> None:
    global global_login_status
    global_login_status = status


def check_valid_user(client: socket.socket, login_status: str, data: str) -> bool:
    global global_username, global_password
    if login_status == "not_logged_in":
        client.sendall(b'Voer je gebruikersnaam in: ')
        update_login_status("logging_in_username")
    elif login_status == "logging_in_username":
        global_username = data.strip()
        client.sendall(b'Voer je wachtwoord in: ')
        update_login_status("logging_in_password")
    elif login_status == "logging_in_password":
        global_password = data.strip()
        if global_username != "admin" or global_password != "password":
            client.sendall(b'Ongeldige gebruikersnaam of wachtwoord!\r\n')
            client.sendall(b'Jan Willem> ')
            update_login_status("not_logged_in")
            return False
        else:
            update_login_status("logged_in")
            return True
    elif login_status == "logged_in":
        return True
    return False

def start_program(client: socket.socket, program: str) -> None:
    if program in ALLOWED_PROGRAMS:
        subprocess.Popen([program], shell=True)
        client.sendall(f"programma {program} gaat starten!\r\n".encode())
    elif program == "onbekend":
        client.sendall(b"geen programma opgegeven!\r\n")
    else:
        client.sendall(f"programma {program} is niet toegestaan!\r\n".encode())
    client.sendall(b'Jan Willem> ')


def do_something(client: socket.socket, data: str) -> None:
    global global_login_status, last_started_program
    if data.startswith("stop"):
        client.sendall(b"Server gaat stoppen, tot ziens!\r\n")
        client.close()
        sys.exit(0)
    elif data == "":
        client.sendall(b'Jan Willem> ')
    elif data.startswith("start") or global_login_status == "logging_in_username" or global_login_status == "logging_in_password":
        if data.startswith("start"):
            program = data.split(" ")[1] if len(data.split(" ")) > 1 else "onbekend"
            last_started_program = program
            print(f'> Gebruiker probeert programma te starten: {program}')
        valid_user = check_valid_user(client, login_status=global_login_status, data=data)
        if  valid_user:
            print(f'> Gebruiker is geldig, start programma: {last_started_program}')
            assert last_started_program is not None
            program_to_start: str = last_started_program
            start_program(client, program_to_start)
    else:
        client.sendall(b"jeStuurdeMijDezeData:" + data.encode())
        client.sendall(b'\r\n')
        client.sendall(b'Jan Willem> ')

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # avoid TIME_WAIT error

try:
    s.bind((HOST, PORT))
except OSError as e:
    print(f'> Kan niet binden op poort {PORT}: {e}', file=sys.stderr)
    sys.exit(1)

s.listen(10)
print('> Socket luistert op poort:', PORT)

# Wacht op connecties (blocking)
conn, addr = s.accept()
print('> Verbonden met ' + addr[0] + ':' + str(addr[1]))

conn.sendall(b'WelkomOpMijnServer, vertel me iets, dan zeg ik hetzelfde terug:\r\n')
conn.sendall(b'\r\n\n\n')
conn.sendall(b'Jan Willem> ')

# Wacht op input van de client en geef deze ook weer terug (echo service)
total_data = bytearray()  # editable buffer instead of bytes

BACKSPACE = 0x08
DEL = 0x7F

while True:
    print('> Wacht op input van de client...')
    connection_data_stream = conn.recv(1024)
    if not connection_data_stream:
        break

    for byte in connection_data_stream:
        if byte in (BACKSPACE, DEL):
            if total_data:
                total_data.pop()  # remove last character
                # optional: echo the erase back to the client's terminal
                conn.sendall(b'\x08 \x08')
        elif byte in (ord('\r'), ord('\n')):
            # treat CR or LF as end-of-line
            if total_data or byte == ord('\n'):
                do_something(client=conn, data=total_data.decode("ascii", errors="replace"))
                total_data = bytearray()
        else:
            total_data.append(byte)


time.sleep(1)  # nodig op sommige computers, voorkomt verbreken verbinding te vroeg

# Verbreek de verbinding en sluit de socket
conn.close()
s.close()