import pexpect
import os
import argparse
import json
import random
import string
from pexpect.exceptions import TIMEOUT as TimeoutException, EOF as EndOfFileException
import time

CLIENT_FOLDER_PATH = './'
ADDRESS = "127.0.0.1"
PORT = 5378
STUDENT_FILE_PATH = "../student/server_check/server.py"

def generate_name():
    return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16)))

def generate_message(min_len=32, max_len=64):
    return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(min_len, max_len)))

class TestException(Exception):
    pass

def handle_pexpect(child_process, processes_to_terminate, expect_string, output_buffer, step, timeout=1):
    try:
        child_process.expect(expect_string, timeout=timeout)
        output_buffer += child_process.before + child_process.after

    except TimeoutException:
        output_buffer += child_process.before
        last_printed_line = '[EMPTY LINE. PROGRAM DID NOT PRODUCE ANY OUTPUT]'
        lines = output_buffer.split('\n')

        for line in reversed(lines):
            if line.strip():
                last_printed_line = line
                break

        for process in processes_to_terminate:
            process.terminate(force=True)

        raise TestException(f'unexpected client output at the step {step}!\nExpected output:\n\n{expect_string}\n\nActual output (the last printed line): \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    except EndOfFileException:
        output_buffer += child_process.before + child_process.after

        for process in processes_to_terminate:
            process.terminate(force=True)
            
        raise TestException(f'program has unexpectidly terminated at step {step}!\nExpected output:\n\n{expect_string}\n\nProgram\'s last printed line: \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    
    return output_buffer

def start_server():
    server_process = execute_and_detach(f'python3 {STUDENT_FILE_PATH} --address "{ADDRESS}" --port {PORT}')
    expected_output = "Server is on"

    output_buffer = handle_pexpect(server_process, [server_process], expected_output, "", "starting a server")
        
    return server_process, output_buffer


def execute_and_wait(cmd):
    process = pexpect.spawn('/bin/sh', ['-c', cmd], encoding='utf-8')
    process.expect(pexpect.EOF)
    output = process.before  # Capture the output
    process.wait()

    return process.exitstatus, output

def execute_and_collect_output(cmd):
    child = pexpect.spawn(cmd, encoding='utf-8')
    while True:
        try:
            line = child.readline()
            if not line:
                break
            yield line
        except pexpect.EOF:
            break

def execute_and_detach(cmd):
    child = pexpect.spawn(cmd, encoding='utf-8')
    return child
    

def start_script():
    expected_output = 'Welcome to Chat Client. Enter your login:'

    current_dir = os.getcwd()
    os.chdir(CLIENT_FOLDER_PATH)

    client_process = pexpect.spawn(f'java -jar ChatClient.jar', encoding='utf-8')

    os.chdir(current_dir)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, "", "starting a client")

    return client_process, output_buffer

def log_in(client_name="client"):
    expected_output = f'Succesfully logged in as {client_name}!'

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "logging in with a client")

    return client_process, output_buffer

def reject_usernames_commas():
    client_name = generate_name()
    first_rand_index = random.randint(0, len(client_name) - 1)
    client_name = client_name[:first_rand_index] + "," + client_name[first_rand_index + 1:]

    expected_output = "Error: Unknown issue in previous message header."

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "rejecting client username if there are commas in it")

    return client_process, output_buffer

def reject_usernames_spaces():
    client_name = generate_name()
    first_rand_index = random.randint(0, len(client_name) - 1)
    client_name = client_name[:first_rand_index] + " " + client_name[first_rand_index + 1:]

    expected_output = "Error: Unknown issue in previous message header."

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "rejecting client username if there are spaces in it")

    return client_process, output_buffer

def reject_usernames_new_lines():
    client_name = generate_name()
    first_rand_index = random.randint(0, len(client_name) - 1)
    client_name = client_name[:first_rand_index] + "\\n" + client_name[first_rand_index + 1:]

    expected_output = "Error: Unknown issue in previous message header."

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "rejecting client username if there are newline symbols in it")

    return client_process, output_buffer

def test_16_clients():
    MAX_CLIENTS = 16
    client_nameS = [generate_name() for _ in range(MAX_CLIENTS)]

    [log_in(f'{client_nameS[i]}') for i in range(0, 16)]

def test_busy():
    MAX_CLIENTS = 16

    client_names = [generate_name() for _ in range(MAX_CLIENTS)]
    logged_processes = [log_in(f'{client_names[i]}') for i in range(0, 16)]

    client_name = generate_name()
    expected_output = "Cannot log in. The server is full!"

    busy_process, output_buffer = start_script()
    busy_process.sendline(client_name)

    output_buffer = handle_pexpect(busy_process, [busy_process], expected_output, output_buffer, "logging into busy server")

    [process.terminate() for process, _ in logged_processes]

    return busy_process, output_buffer

def disconnect():
    client_name = generate_name()
    client_name_2 = generate_name()
    
    expected_output = "The destination user does not exist."

    client_process_1, output_buffer_1 = log_in(client_name)
    client_process_2, _ = log_in(client_name_2)

    client_process_2.sendline('!quit')
    client_process_2.terminate()

    time.sleep(10) # this should give server enough time to handle a disconnection

    client_process_1.sendline(f'@{client_name_2} {generate_message()}')

    output_buffer_1 = handle_pexpect(client_process_1, [client_process_1], expected_output, output_buffer_1, "disconnecting a client and sending a message to disconnected client")

    client_process_1.terminate()

    return client_process_1, output_buffer_1

def log_in_duplicate():
    client_name = generate_name()
    expected_output = f'Cannot log in as {client_name}. That username is already in use.'

    client_process_1, output_buffer_1 = log_in(client_name)

    client_process_2, output_buffer_2 = start_script()
    client_process_2.sendline(client_name)

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_2, 
                   f'logging a client in with a duplicate name {client_name}')

    client_process_1.terminate()
    client_process_2.terminate()

    return client_process_1, output_buffer_1

def list_users():
    client_name_1 = generate_name()
    client_name_2 = generate_name()
    client_name_3 = generate_name()

    client_process_1, _ = log_in(client_name_1)
    client_process_2, _ = log_in(client_name_2)

    client_process_3, output_buffer_3 = log_in(client_name_3)
    client_process_3.sendline('!who')

    output_buffer_3 = handle_pexpect(client_process_3, [client_process_1, client_process_2, client_process_3], client_name_1, output_buffer_3, f'checking the name {client_name_1} is in output of !who command')
    output_buffer_3 = handle_pexpect(client_process_3, [client_process_1, client_process_2, client_process_3], client_name_2, output_buffer_3, f'checking the name {client_name_2} is in output of !who command')
    output_buffer_3 = handle_pexpect(client_process_3, [client_process_1, client_process_2, client_process_3], client_name_3, output_buffer_3, f'checking the name {client_name_3} is in output of !who command')

    return client_process_3

def test_simple_exchange():
    client_name_1 = generate_name()
    client_name_2 = generate_name()
    TOTAL_MSGS_SENT = 10

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    msgs = [generate_message() for _ in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs])
    expected_output = r'\s*' + expected_output + r'\s*'

    for msg in msgs:
        client_process_1.sendline(f'@{client_name_2} {msg}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "performing a simple message exchange (exchanging 10 messages from one client to another)", 20)

    return client_process_2, output_buffer_2

def test_longer_exchange_messages():
    client_name_1 = generate_name()
    client_name_2 = generate_name()
    TOTAL_MSGS_SENT = 10

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    msgs = [generate_message(256, 512) for i in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs])
    expected_output = r'\s*' + expected_output + r'\s*'

    for msg in msgs:
        client_process_1.sendline(f'@{client_name_2} {msg}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "performing a simple message exchange (exchanging 10 messages between two clients)", 20)

    return client_process_2, output_buffer_2

def send_message_to_unknown():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    message = generate_message()
    expected_output = "The destination user does not exist"

    client_process, output_buffer = log_in(client_name_1)
    client_process.sendline(f'@{client_name_2} {message}')

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "sending a message to not-existent user")
    client_process.terminate()

    return client_process, output_buffer

def verify_file_for_sendall():
    file_path = os.path.join(os.getcwd(), STUDENT_FILE_PATH)

    try:
        with open(file_path, 'r') as file:
            code_str = file.read()
        
        if "sendall" in code_str:
            raise TestException("Found 'sendall' in the code.")
        else:
            return True
    except FileNotFoundError:
        raise TestException("File server.py was not found. Please ensure that your implementation is saved under server.py name")
    except Exception as e:
        raise RuntimeError("An error occurred:", e)
    
def error_body():
    client_name_1 = generate_name()
    client_name_2 = "echobot"

    expected_output = "Error: Unknown issue in previous message body."

    client_process_1, output_buffer = log_in(client_name_1)
    client_process_1.sendline(f'@{client_name_2} ')

    output_buffer = handle_pexpect(client_process_1, [client_process_1], expected_output, output_buffer, "sending a message with an error in a body to receive BAD-RQST-BODY response")

    client_process_1.terminate()
    return client_process_1, output_buffer

def send_message_before_login():
    client_name_1 = generate_name()
    message = generate_message()
    
    expected_output = "BAD-RQST-HDR"
    _, output = execute_and_wait(f'echo "SEND {client_name_1} {message}" | nc 127.0.0.1 5378 -W 1')
    
    if not expected_output in output:
        raise TestException(f"your sever did not return BAD-RQST-HDR when trying to send messages before logging in. Answer was '{output}'")

    return output

class TestCase():
    def __init__(self, test_func, test_id, test_msg, tags=[], max_clients=300) -> None:
        self.tags = tags
        self.test_func = test_func
        self.test_id = test_id
        self.test_msg = test_msg
        self.max_clients = max_clients
    
    def execute(self, disable_colors=False):
        success = True
        tags_string = ' '.join(self.tags)

        try:
            server_process, _ = start_server()
        except:
            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nError message is the server did not start. Please make sure your server prints Server is on on startup \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nError message is {e} \nThe server output is {server_process.before}')
            
            return False

        try:
            self.test_func()
            
            if not disable_colors:
                print(f'\033[92m[ \u2713 ] \033[30m{self.test_id}. {self.test_msg}. \033[92mSuccess! \033[0m')
            else:
                print(f'[ \u2713 ] {self.test_id}. {self.test_msg}. Success!')
        
        except TypeError as e: # originates from pexpect .before if script terminates. except for more readable error message
            success = False

            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nYour server did not start \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nYour server did not start')

        except Exception as e:
            try:
                server_process.expect(pexpect.EOF, timeout=0)
            except:
                pass

            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nError message is {e} \nThe server output is {server_process.before} \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nError message is {e} \nThe server output is {server_process.before}')
            
            success = False
        
        if server_process:
            server_process.terminate(force=True)

        return success

test_cases = [
    TestCase(start_script, "chat_server_001", "Server starts successfuly"),
    TestCase(log_in, "chat_server_002", "Log in with unique name and expect success", ['PR2', 'PR3']),
    TestCase(log_in_duplicate, "chat_server_003", "Log in with duplicate name and expect failure", ['PR5']),
    TestCase(list_users, "chat_server_004", "Log in, list users and expect success", ['PR8', 'PR9']),
    TestCase(test_simple_exchange, "chat_server_005", "Send message to other user and expect success", ['PR10', 'PR11', 'PR12']),
    TestCase(test_longer_exchange_messages, "chat_server_006", "Send long message to other user and expect success", ['PR10', 'PR11', 'PR12']),
    TestCase(send_message_to_unknown, "chat_server_007", "Send message to non-existent user and expect failure", ['PR13', 'PR14']),
    TestCase(verify_file_for_sendall, "chat_server_008", "The server must not use the sendall() function in Python", []),
    TestCase(error_body,  "chat_server_009", "Last message received from the client contains an error in the body", ['PR4']),
    TestCase(reject_usernames_spaces, "chat_server_010", "Server does not accept usernames with spaces", ['PR6', 'PR16']),
    TestCase(reject_usernames_new_lines, "chat_server_011", "Server does not accept usernames with new lines", ['PR6', 'PR16']),
    TestCase(reject_usernames_commas, "chat_server_012", "Server does not accept usernames with commas", ['PR6']),
    TestCase(test_16_clients, "chat_server_013", "Server supports 16 clients", ['TR1', 'TR2']),
    TestCase(test_busy, "chat_server_014", "Server responds with busy for 17 clients", ['PR15']),
    TestCase(disconnect, "chat_server_015", "Server accepts disconnections", ['TR3']),
    TestCase(send_message_before_login, "chat_server_016", "Server responds with a bad header if the message sent by the client who is not logged in", ['PR7'])
]

parser = argparse.ArgumentParser(description='Process test arguments')

parser.add_argument('--case', type=str, help='Test case name', default=None)
parser.add_argument('--tags', type=str, help='List of tags', default=None)
parser.add_argument('--clientfolder', type=str, help='Client path', default=None)
parser.add_argument('--disablecolors', type=str, help='(optional) disable colors for the codegrade', default=False)
args = parser.parse_args()

case = args.case
disable_colors = args.disablecolors
client_folder = args.clientfolder

if client_folder:
    CLIENT_FOLDER_PATH = client_folder

if args.tags:
    try:
        # Assuming the tags are passed in a format that's convertible to a Python list
        tags_list = json.loads(args.tags.replace("'", "\""))
    except json.JSONDecodeError as e:
        print(f"Error parsing tags: {e}")
        tags_list = None
else:
    tags_list = None

def execute_tests(test_cases, case, tags_list, disable_colors):
    success = True
    for test in test_cases:
        if tags_list is not None and len([tag for tag in test.tags if tag in tags_list]) > 0 and case is None:
            if not test.execute(disable_colors=disable_colors):
                success = False
        elif case is not None and case == test.test_id:
            if not test.execute(disable_colors=disable_colors):
                success = False
            break
        elif case is None and tags_list is None:
            if not test.execute(disable_colors=disable_colors):
                success = False
        else:
            continue
    
    return success


if not execute_tests(test_cases=test_cases, case=case, tags_list=tags_list, disable_colors=disable_colors):
    exit(1)
else:
    exit(0)

