import argparse

parser = argparse.ArgumentParser(description='Process test arguments')
parser.add_argument('--address', type=str, help='Server IP address', default='212.132.114.68')
parser.add_argument('--port', type=int, help='Server Port', default=5382)

# you can start your client by passing the arguments --address and --port which should be
# chat server server IP address and server port you want your client to connect to. 
# The default values are our remote server with 212.132.114.68 for address and 5382 for port.
# Tests will start a local server and pass its address and port as arguments to the program
# in a form of python3 client.py --address="127.0.0.1" --port 5382

args = parser.parse_args()

SERVER_HOST = args.address
SERVER_PORT = args.port

# SERVER_HOST and SERVER_PORT contain address and port arguments

print('Welcome to Chat Client. Enter your login:')
# Please put your code in this file
