# tcp_protocol.py

import socket
from cmd import handle_command

def tcp_ip_thread():
    """
    This thread handles TCP/IP communication with the Raspberry Pi.
    """
    host = '127.0.0.1'  # Localhost for testing, change to Raspberry Pi IP
    port = 12345        # Port to listen on

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    
    while True:
        client_socket, addr = server_socket.accept()
        print(f"Connection from {addr} has been established!")
        
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            
            command = data.decode('utf-8')
            response = handle_command(command)
            
            client_socket.sendall(response.encode('utf-8'))
        
        client_socket.close()
