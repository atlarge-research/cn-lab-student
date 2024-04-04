import pexpect
import os
import argparse
import json
import random
import string
from pexpect.exceptions import TIMEOUT as TimeoutException, EOF as EndOfFileException

SERVER_ADDRESS = '127.0.0.1'
SERVER_PORT = 5378

STUDENT_FILE_PATH = "../student/chat_client_check/client.py"

class TestException(Exception):
    pass

def generate_name():
    return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16)))

def generate_message(min_len=32, max_len=64):
    return ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(min_len, max_len)))

def handle_pexpect(child_process, processes_to_terminate, expect_string, output_buffer, step, timeout=1, display_expect_string=''):
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

        if display_expect_string:
            expect_string = display_expect_string

        raise TestException(f'unexpected output at step {step}!\nExpected output:\n\n{expect_string}\n\nActual output (the last printed line): \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    except EndOfFileException:
        output_buffer += child_process.before + child_process.after

        for process in processes_to_terminate:
            process.terminate(force=True)
            
        raise TestException(f'program has unexpectidly terminated at step {step}!\nExpected output:\n\n{expect_string}\n\nProgram\'s last printed line: \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    
    return output_buffer
    

def start_server(maxClients=300):
    server_process = execute_and_detach(f'java -jar ChatServer.jar {maxClients}')
    server_process.expect("Now listening on port 5378")
    echobot_process = execute_and_detach("java -jar EchoBot.jar 127.0.0.1 5378")

    return server_process,echobot_process


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
    client_process = pexpect.spawn(f'python3 {STUDENT_FILE_PATH} --address "{SERVER_ADDRESS}" --port {SERVER_PORT}', encoding='utf-8')

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, "", "starting client script")

    return client_process, output_buffer

def log_in(client_name=generate_name()):
    expected_output = f'Successfully logged in as {client_name}!'

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)
    
    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, 
                   f'logging a client in with a name {client_name}')

    return client_process, output_buffer

def log_in_duplicate():
    client_name = generate_name()
    expected_output = f'Cannot log in as {client_name}. That username is already in use.'

    client_process_1, output_buffer_1 = log_in(client_name)

    client_process_2, output_buffer_2 = start_script()
    client_process_2.sendline(client_name)

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_2, 
                   f'logging a client a duplicate name {client_name}')

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

    clients_list = [[client_name_1, client_process_1], [client_name_2, client_process_2], [client_name_3, client_process_3]]

    [handle_pexpect(client_process_3, [process for _, process in clients_list], name, output_buffer_3, f'checking that the name {name} appears in !who output') for name, _ in clients_list]

    return client_process_3

def test_busy():
    client_name = generate_name()

    expected_output = "Cannot log in. The server is full!"

    busy_process, output_buffer = start_script()
    busy_process.sendline(client_name)

    output_buffer = handle_pexpect(busy_process, [busy_process], expected_output, output_buffer, "logging into busy server")

    try:
        busy_process.expect(pexpect.EOF, timeout=1)
    except TimeoutException:
        busy_process.terminate(force=True)
        raise TestException(f'client should have been terminated; however, it continued its execution!')

    busy_process.terminate()

    return busy_process, output_buffer

def test_simple_exchange():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    TOTAL_MSGS_SENT = 10

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    msgs = [generate_message() for _ in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs])
    expected_output_to_show = ''.join([f'From {client_name_1}: {msg}\n' for msg in msgs])

    expected_output = r'\s*' + expected_output + r'\s*'

    [client_process_1.sendline(f'@{client_name_2} {msg}') for msg in msgs]

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "simple message exchange (exchanging 10 messages between 2 clients)", 20, display_expect_string=expected_output_to_show)

    return client_process_2, output_buffer_2

def test_longer_exchange_messages():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    TOTAL_MSGS_SENT = 10

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    msgs = [generate_message(256, 512) for _ in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs])
    expected_output_to_show = ''.join([f'From {client_name_1}: {msg}\n' for msg in msgs])

    expected_output = r'\s*' + expected_output + r'\s*'

    for msg in msgs:
        client_process_1.sendline(f'@{client_name_2} {msg}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "simple message exchange with long messages (exchanging 10 messages between 2 clients)", 20, display_expect_string=expected_output_to_show)

    return client_process_2, output_buffer_2

def send_message_to_unknown():
    client_name_1 = generate_name()
    client_name_2 = generate_name()
    MESSAGE = generate_message()

    expected_output = "The destination user does not exist"

    client_process, output_buffer = log_in(client_name_1)
    client_process.sendline(f'@{client_name_2} {MESSAGE}')

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "sending a message to not existent user")
    client_process.terminate()

    return client_process, output_buffer


def exchange_message_echobot():
    client_name_1 = generate_name()
    ECHOBOT_NAME = "echobot"
    MESSAGE = generate_message()

    expected_output = f'From {ECHOBOT_NAME}: {MESSAGE}'

    client_process, output_buffer = log_in(client_name_1)
    client_process.sendline(f'@{ECHOBOT_NAME} {MESSAGE}')

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "sending and receiving message from echobot")
    client_process.terminate()

    return client_process, output_buffer

def not_restart_failed_attempt():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    expected_output_IN_USE = f'Cannot log in as {client_name_1}. That username is already in use.'
    expected_output_SUCCESS = f'Successfully logged in as {client_name_2}!'

    client_process_1, _ = log_in(client_name_1)

    client_process_2, output_buffer_2 = start_script()
    client_process_2.sendline(client_name_1)

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_IN_USE, output_buffer_2, "logging in with duplicate name")

    client_process_2.sendline(client_name_2)

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_SUCCESS, output_buffer_2, "logging again after receiving IN-USE message")

    client_process_1.terminate(force=True)
    client_process_2.terminate(force=True)

    return client_process_1, output_buffer_2

def check_name():
    client_name = "@!"
    expected_output = f'Cannot log in as {client_name}. That username contains disallowed characters.'

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "logging in client containing dissallowed characters in name")

    return client_process, output_buffer

def verify_file_for_sendall():
    file_path = os.path.join(os.getcwd(), STUDENT_FILE_PATH)

    try:
        with open(file_path, 'r') as file:
            code_str = file.read()
        
        if "sendall" in code_str:
            raise AssertionError("Found 'sendall' in the code.")
        else:
            return True
    except FileNotFoundError:
        raise TestException("File client.py. Please ensure that your implementation is located in the same folder under client.py name")
    except Exception as e:
        raise RuntimeError("An error occurred:", e)
    
def error_body():
    client_name_1 = generate_name()
    client_name_2 = "echobot"

    expected_output = "Error: Unknown issue in previous message body."

    client_process_1, output_buffer = log_in(client_name_1)
    client_process_1.sendline(f'@{client_name_2} ')

    output_buffer = handle_pexpect(client_process_1, [client_process_1], expected_output, output_buffer, "handling BAD-RQST-BODY server response")

    client_process_1.terminate()
    return client_process_1

def quit_before_log_in():
    client_name_1 = "!quit"

    client_process, _ = start_script()
    client_process.sendline(client_name_1)

    try:
        client_process.expect(pexpect.EOF)
    except TimeoutException:
        client_process.terminate(force=True)
        raise TestException("Client was expected to terminate but it did not!")
    
    client_process.terminate()

    return client_process

def quit_after_log_in():
    client_name_1 = generate_name()

    client_process, output_buffer = log_in(client_name_1)
    client_process.sendline('!quit')

    try:
        client_process.expect(pexpect.EOF)
    except TimeoutException:
        client_process.terminate(force=True)
        raise TestException("Client was expected to terminate but it did not!")
    
    client_process.terminate()

    return client_process, output_buffer

def check_message_concurrency():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    message_1 = generate_message()
    message_2 = generate_message()

    expected_output_1 = f'From {client_name_1}: {message_1}'
    expected_output_2 = f'From {client_name_1}: {message_1}'
    expected_output_3 = f'From {client_name_2}: {message_2}'

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)
    
    client_process_1.sendline(f'@{client_name_2} {message_1}')
    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_1, output_buffer_2, "(testing concurrency) sending a message from first client to second")
    
    client_process_1.sendline(f'@{client_name_2} {message_1}')
    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_2, output_buffer_2, "(testing concurrency) sending a message from second client to first after sending a message from first client to second")

    client_process_2.sendline(f'@{client_name_1} {message_2}')
    output_buffer_1 = handle_pexpect(client_process_1, [client_process_1, client_process_2], expected_output_3, output_buffer_1, "(testing concurrency) sending a message from first client to second after sending a message from second client to first after sending a message from first client to second")
    
    client_process_1.terminate()
    client_process_2.terminate()
    
    return client_process_1, output_buffer_1

class TestCase():
    def __init__(self, test_func, test_id, test_msg, tags=[], max_clients=300) -> None:
        self.tags = tags
        self.test_func = test_func
        self.test_id = test_id
        self.test_msg = test_msg
        self.max_clients = max_clients
    
    def execute(self, disable_colors):
        success = True
        server_process,echobot = start_server(self.max_clients)
        tags_string = ' '.join(self.tags)
        
        try:
            self.test_func()

            if not disable_colors:
                print(f'\033[92m[ \u2713 ] \033[30m{self.test_id}. {self.test_msg}. \033[92mSuccess! \033[0m')
            else:
                print(f'[ \u2713 ] {self.test_id}. {self.test_msg}. Success!')

        except TypeError as e: # originates from pexpect .before if script terminates. except for more readable error message
            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nYour client did not start or connected to a wrong server port \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nYour client did not start or connected to a wrong server port')
            
            success = False

        except Exception as e:
            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nError message is {e} \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nError message is {e}')

            success = False
                
        server_process.terminate(force=True)
        echobot.terminate(force = True)

        return success


test_cases = [
    TestCase(start_script, "chat_001", "Start application and expect welcome message", ['RA1', 'RI2', 'RT7']),
    TestCase(log_in, "chat_002", "Log in with unique name and expect success message", ['RI1', 'RT7', 'RI3']),
    TestCase(check_name, "chat_003", "A client must inform the user if their username was rejected for any other reason and ask for a new username - forbidden symbols (!@#$%^&*)", ['RI1', 'RT7', 'RA4', 'RT1']),
    TestCase(log_in_duplicate, "chat_004", "Log in with duplicate name and expect in use messsage", ['RI1', 'RT7', 'RA2', 'RI4']),
    TestCase(not_restart_failed_attempt, "chat_005", "Expect client to not restart after a failed log in attempt", ['RI1', 'RT7', 'RA6']),
    TestCase(test_busy, "chat_006", "Log in with busy server, expect failure, and shut client down gracefully", ['RI1', 'RT7', 'RI6'], max_clients=0),
    TestCase(list_users, "chat_007", "List users and expect success", ['RI1', 'RT7', 'RC2', 'RI11']),
    TestCase(test_simple_exchange, "chat_008", "Send message to other user and expect success", ['RI1', 'RT7', 'RI2', 'RI8', 'RI10']),
    TestCase(test_longer_exchange_messages, "chat_009", "Send long message to other user and expect success", ['RI1', 'RT7', 'RI2', 'RI8', 'RI10']),
    TestCase(exchange_message_echobot,"chat_010", "A client should be able to send a message to echobot and receive the full message", ['RI1', 'RT7', 'RA7']),
    TestCase(send_message_to_unknown, "chat_011", "Send message to non-existent user and expect failure", ['RI1', 'RT7', 'RI9']),
    TestCase(verify_file_for_sendall, "chat_012", "A client must not use the sendall() function in Python", ['RI1', 'RT7', 'RT2']),
    TestCase(error_body,  "chat_013", "Last message received from the client contains an error in the body", ['RI1', 'RT7', 'R13']),
    TestCase(quit_after_log_in, "chat_014", "A client can exit after log in", ['RI1', 'RT7', 'RC1', 'RA8']),    
    TestCase(quit_before_log_in, "chat_015", "A client can exit before log in", ['RI1', 'RT7', 'RC1', 'RA8']),
    TestCase(check_message_concurrency, "chat_016", "Send message from C1 and then send 2-3 messages to client C1 from C2. Check those are displayed straight away", ['RI1', 'RT7', 'RT6'])
]


parser = argparse.ArgumentParser(description='Process test arguments')

parser.add_argument('--case', type=str, help='Test case name', default=None)
parser.add_argument('--tags', type=str, help='List of tags', default=None)
parser.add_argument('--disablecolors', type=bool, help='(is used only for printing formatting in codegrade)', default=False)
args = parser.parse_args()

case = args.case
disable_colors = args.disablecolors

if args.tags:
    try:
        tags_list = json.loads(args.tags.replace("'", "\""))
    except json.JSONDecodeError as e:
        print(f"Error parsing tags: {e}")
        tags_list = None
else:
    tags_list = None

def execute_tests(test_cases, case, tags_list):
    SUCCESS = True
    for test in test_cases:
        if tags_list is not None and len([tag for tag in test.tags if tag in tags_list]) > 0 and case is None:
            if not test.execute(disable_colors=disable_colors):
                SUCCESS = False
        elif case is not None and case == test.test_id:
            if not test.execute(disable_colors=disable_colors):
                SUCCESS = False
            break
        elif case is None and tags_list is None:
            if not test.execute(disable_colors=disable_colors):
                SUCCESS = False
        else:
            continue
    
    return SUCCESS


if not execute_tests(test_cases=test_cases, case=case, tags_list=tags_list):
    exit(1)
else:
    exit(0)
