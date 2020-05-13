import os
import time
import socket                   # Import socket module

port = 60000                    # Reserve a port for your service.
s = socket.socket()             # Create a socket object
host = "0.0.0.0"#socket.gethostname()     # Get local machine name
s.bind((host, port))            # Bind to the port
s.listen(5)                     # Now wait for client connection.

print 'Server listening....'
filename=r"C:\Program Files\Keyhole\keyhole.exe"

while True:

    try:
        conn, addr = s.accept()     # Establish connection with client.
        print "Got connection from", addr
    except KeyboardInterrupt:
        break
    
    print "Killing Keyhole..."
    os.system("taskkill /IM keyhole.exe /F")
    time.sleep(1)

    data = []
    while True:
        data.append(conn.recv(1024))
        if not data[-1]:
            data.pop()
            break

    with open(filename, 'wb') as f:
        f.write(''.join(data))

    print "Saved to disk..."
    conn.close()

    print "Launching Keyhole..."
    os.system('"%s"' % filename)
