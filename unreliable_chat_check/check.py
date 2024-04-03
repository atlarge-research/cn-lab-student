import pexpect
import os
import argparse
import json
import random
import signal
import string
from pexpect.exceptions import TIMEOUT as TimeoutException, EOF as EndOfFileException

class TestException(Exception):
    pass

SERVER_DIRECTORY = "./"
SERVER_ADDRESS = "127.0.0.1"
SERVER_PORT = 5382

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

def start_server(maxClients=300, burst=0, delay=0, flip=0, drop=0, delayLenLower=0, delayLenUpper=0, burstLenLower=0, burstLenUpper=0):
    current_dir = os.getcwd()
    os.chdir(SERVER_DIRECTORY)

    server_process = execute_and_detach(f'go run BrokenChatServerLocal.go -address="{SERVER_ADDRESS}" -port="{SERVER_PORT}" -maxClients={maxClients} -burst={burst} -flip={flip} -delay={delay} -drop={drop} -delayLenLower={delayLenLower} -delayLenUpper={delayLenUpper} -burstLenLower={burstLenLower} -burstLenUpper={burstLenUpper}')
    server_process.expect("The server is running on")

    os.chdir(current_dir)

    return server_process


def execute_and_wait(cmd):
    process = pexpect.spawn('/bin/sh', ['-c', cmd], encoding='utf-8')
    process.expect(pexpect.EOF)
    process.wait()

    return process.exitstatus

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
    expected_output = f'Welcome to Chat Client. Enter your login:'
    client_process = pexpect.spawn(f'python3 client.py --address "{SERVER_ADDRESS}" --port {SERVER_PORT}', encoding='utf-8')

    output_buffer = handle_pexpect(client_process, [client_process], f'{expected_output}', "", "starting the client script")

    return client_process, output_buffer

def log_in(client_name=generate_name()):
    expected_output = f'Succesfully logged in as {client_name}!'

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, 
                   f'logging the client in with the name {client_name}')
    

    return client_process, output_buffer

def log_in_duplicate():
    client_name = generate_name()
    expected_output = f'Cannot log in as {client_name}. That username is already in use.'

    client_process_1, output_buffer_1 = log_in(client_name)

    client_process_2, output_buffer_2 = start_script()
    client_process_2.sendline(client_name)

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_2, 
                   f'logging the client the duplicate name {client_name}')

    client_process_1.terminate()
    client_process_2.terminate()

    return client_process_1, output_buffer_1

def test_busy():
    client_name = generate_name()

    expected_output = f'Cannot log in. The server is full!'

    busy_process, output_buffer = start_script()
    busy_process.sendline(client_name)

    output_buffer = handle_pexpect(busy_process, [busy_process], expected_output, output_buffer, "attemting to log into the busy server")

    try:
        busy_process.expect(pexpect.EOF, timeout=1)
    except TimeoutException:
        busy_process.terminate(force=True)
        raise TestException(f'client should been have terminated; however, it continued its execution!')

    busy_process.terminate()

    return busy_process, output_buffer

def test_simple_exchange():
    TOTAL_MSGS_SENT = 5

    client_name_1 = generate_name()
    client_name_2 = generate_name()

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    msgs = [generate_message(16, 32) for _ in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs])
    expected_output_TO_SHOW = ''.join([f'From {client_name_1}: {msg} \n' for msg in msgs])
    expected_output = r'\s*' + expected_output + r'\s*'

    for msg in msgs:
        client_process_1.sendline(f'@{client_name_2} {msg}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "performing a simple message exchange (exchanging 5 messages from one client to another)", 20, display_expect_string=expected_output_TO_SHOW)

    return client_process_2, output_buffer_2

def test_exchange_with_multiple():
    TOTAL_MSGS_SENT = 5

    client_name_1 = generate_name()
    client_name_2 = generate_name()
    client_name_3 = generate_name()

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)
    client_process_3, output_buffer_3 = log_in(client_name_3)

    msgs_to_client_2 = [''.join(random.choice(string.ascii_letters) for _ in range(random.randint(16, 32))) for i in range(TOTAL_MSGS_SENT)]
    expected_output_client_2 = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs_to_client_2])
    expected_output_to_show_2 = ''.join([f'From {client_name_1}: {msg}\n' for msg in msgs_to_client_2])
    expected_output_client_2 = r'\s*' + expected_output_client_2 + r'\s*'

    msgs_to_client_3 = [''.join(random.choice(string.ascii_letters) for _ in range(random.randint(16, 32))) for i in range(TOTAL_MSGS_SENT)]
    expected_output_client_3 = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in msgs_to_client_3])
    expected_output_to_show_3 = ''.join([f'From {client_name_1}: {msg}\n' for msg in msgs_to_client_3])
    expected_output_client_3 = r'\s*' + expected_output_client_3 + r'\s*'

    for index_msg in range(TOTAL_MSGS_SENT):
        client_process_1.sendline(f'@{client_name_2} {msgs_to_client_2[index_msg]}')
        client_process_1.sendline(f'@{client_name_3} {msgs_to_client_3[index_msg]}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2, client_process_3], expected_output_client_2, output_buffer_2, "performing a simple message exchange between three clients and reading output of the second client", 20, display_expect_string=expected_output_to_show_2)
    output_buffer_3 = handle_pexpect(client_process_3, [client_process_1, client_process_2, client_process_3], expected_output_client_3, output_buffer_3, "performing a simple message exchange between mutliple clients and reading output of the third client", 20, display_expect_string=expected_output_to_show_3)

    return client_process_1, output_buffer_1


def test_longer_exchange_messages():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    TOTAL_MSGS_SENT = 10

    client_process_1, output_buffer_1 = log_in(client_name_1)
    client_process_2, output_buffer_2 = log_in(client_name_2)

    MSGS = [generate_message(256, 512) for _ in range(TOTAL_MSGS_SENT)]
    expected_output = ''.join([rf'\s*From\s+{client_name_1}:\s+{msg}\s*\n' for msg in MSGS])
    expected_output = r'\s*' + expected_output + r'\s*'

    for msg in MSGS:
        client_process_1.sendline(f'@{client_name_2} {msg}')

    output_buffer_2 = handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output, output_buffer_1, "performing a simple message exchange (exchanging 10 messages from one client to another)", 20)

    return client_process_2, output_buffer_2

def send_message_to_unknown():
    client_name_1 = generate_name()
    client_name_2 = generate_name()
    MESSAGE = generate_message()

    expected_output = "The destination user does not exist"

    client_process, output_buffer = log_in(client_name_1)
    client_process.sendline(f'@{client_name_2} {MESSAGE}')

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "sending message to not existent user")
    client_process.terminate()

    return client_process, output_buffer

def not_restart_failed_attempt():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    expected_output_IN_USE = f'Cannot log in as {client_name_1}. That username is already in use.'
    expected_output_success = f'Succesfully logged in as {client_name_2}'

    client_process_1, _ = log_in(client_name_1)

    client_process_2, output_buffer_2 = start_script()
    client_process_2.sendline(client_name_1)

    handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_IN_USE, output_buffer_2, "logging in with name in use")

    client_process_2.sendline(client_name_2)

    handle_pexpect(client_process_2, [client_process_1, client_process_2], expected_output_success, output_buffer_2, "not exiting after receiving IN-USE message")

    client_process_1.terminate(force=True)
    client_process_2.terminate(force=True)

    return client_process_1

def check_name():
    client_name = generate_name()

    first_rand_index = random.randint(0, len(client_name) - 1)
    second_rand_index = random.randint(0, len(client_name) - 1)

    client_name = client_name[:first_rand_index] + "@" + client_name[first_rand_index + 1:]
    client_name = client_name[:second_rand_index] + "!" + client_name[second_rand_index + 1:]

    expected_output = f'Cannot log in as {client_name}. That username contains disallowed characters.'

    client_process, output_buffer = start_script()
    client_process.sendline(client_name)

    output_buffer = handle_pexpect(client_process, [client_process], expected_output, output_buffer, "logging in with the name with disallowed characters")

    return client_process, output_buffer

def verify_file_for_sendall():
    file_path = os.path.join(os.getcwd(), "client.py")

    try:
        with open(file_path, 'r') as file:
            code_str = file.read()
        
        if "sendall" in code_str:
            raise AssertionError("Found 'sendall' in the code.")
        else:
            return True
    except FileNotFoundError:
        raise TestException("file client.py. Please ensure that your implementation is located in the same folder under client.py name")
    except Exception as e:
        raise RuntimeError("An error occurred:", e)
    
def error_body():
    client_name_1 = generate_name()
    client_name_2 = generate_name()

    expected_output = "Error: Unknown issue in previous message body."

    client_process_1 = log_in(client_name_1)

    client_process_1.sendline(f'@{client_name_2} ')

    try:
        client_process_1.expect(expected_output, timeout=1)
    except TimeoutException:
        client_process_1.terminate(force=True)
        raise TestException(f'unexpected reciever client output when attempting to send erroneous message with the empty body! Expected output: \'{expected_output}\'. Actual output: {client_process_1.readline()}')
    except EndOfFileException:
        client_process_1.terminate(force=True)
        raise TestException(f'program has unexpectidly terminated when attempting to send erroneous message with the empty body! Expected output: \'{expected_output}\'. Program\'s last output: {client_process_1.before}')

    client_process_1.terminate()

    return client_process_1

def quit_before_log_in():
    client_name_1 = "!quit"

    client_process = start_script()
    client_process.sendline(client_name_1)

    try:
        client_process.expect(pexpect.EOF)
    except TimeoutException:
        client_process.terminate(force=True)
        raise TestException("client was expected to terminate but did not!")
    
    client_process.terminate()

def quit_after_log_in():
    client_name_1 = generate_name()

    client_process = log_in(client_name_1)
    client_process.sendline('!quit')

    try:
        client_process.expect(pexpect.EOF)
    except TimeoutException:
        client_process.terminate(force=True)
        raise TestException("client was expected to terminate but did not!")
    
    client_process.terminate()

    return client_process

class TestCase():
    def __init__(self, test_func, test_id, test_msg, tags=[], max_clients=300, burst=0, delay=0, flip=0, drop=0, delayLenLower=0, delayLenUpper=0, burstLenLower=0, burstLenUpper=0) -> None:
        self.tags = tags
        self.test_func = test_func
        self.test_id = test_id
        self.test_msg = test_msg

        self.max_clients = max_clients
        self.burst = burst
        self.delay = delay
        self.flip = flip
        self.drop = drop
        self.delayLenLower = delayLenLower
        self.delayLenUpper = delayLenUpper
        self.burstLenLower = burstLenLower
        self.burstLenUpper = burstLenUpper
    
    def execute(self, disable_colors=False):
        success = True
        tags_string = ' '.join(self.tags)

        server_process = start_server(
            maxClients=self.max_clients,
            burst=self.burst,
            delay=self.delay,
            flip=self.flip,
            drop=self.drop,
            delayLenLower=self.delayLenLower,
            delayLenUpper=self.delayLenUpper,
            burstLenLower=self.burstLenLower,
            burstLenUpper=self.burstLenUpper
        )
        
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
        
        server_process.kill(signal.SIGKILL)

        return success


test_cases = [
    TestCase(start_script, "chat_unreliable_001", "Start client and expect welcome message", ['RA1', 'RI2', 'RT7']),
    TestCase(log_in, "chat_unreliable_002", "Log in with unique name and expect success message", ['RT1', 'RI1', 'RT7', 'RI3']),
    TestCase(check_name, "chat_unreliable_003", "The client must inform a user if their username was rejected for any other reason and ask for a new username - forbidden symbols (!@#$%^&*)", ['RT1', 'RI1', 'RT7', 'RA4', 'RT1']),
    TestCase(log_in_duplicate, "chat_unreliable_004", "Log in with duplicate name and expect in use messsage", ['RT1', 'RI1', 'RT7', 'RA2', 'RI4']),
    TestCase(not_restart_failed_attempt, "chat_unreliable_005", "Expect a client to not restart after a failed log in attempt", ['RT1', 'RI1', 'RT7', 'RA6']),
    TestCase(test_busy, "chat_unreliable_006", "Log in with busy server, expect failure, and shut client down gracefully", ['RT1', 'RI1', 'RT7', 'RI6'], max_clients=0),
    TestCase(test_simple_exchange, "chat_unreliable_007", "Send message to other user and expect success (no unreliabillity settings)", ['RT1', 'RI1', 'RT7', 'RI2', 'RI8', 'RI10']),
    TestCase(send_message_to_unknown, "chat_unreliable_008", "Send message to non-existent user and expect failure", ['RT1', 'RI1', 'RT7', 'RI9']),
    TestCase(test_simple_exchange, "chat_unreliable_009", "Send message to other user and expect success (with bursts from 1 up to 16 bits)", ['RT1', 'RI1', 'RT7', 'RI2', 'RI8', 'RI10', 'RE1', 'RE2', 'RE3'], burst=0.05, burstLenLower=1, burstLenUpper=16),
    TestCase(test_simple_exchange, "chat_unreliable_010", "Sending multiple messages and expecting them to be printed in order (with delay from 0 to 3 seconds)", ['RT1', 'RI1', 'RT7', 'RA2', 'RD1'], delay=1, delayLenLower=0, delayLenUpper=1),
    TestCase(test_simple_exchange, "chat_unreliable_011", "Send message to other user and expect success (with the bitflip 0.0005)", ['RT1', 'RI1', 'RT7', 'RA2', 'RE1', 'RE2', 'RE3'], flip=0.0005),
    TestCase(test_simple_exchange, "chat_unreliable_012", "Send message to other user and expect success (with the drop 0.1)", ['RT1', 'RI1', 'RT7', 'RD1', 'RD3', 'RD5'], drop=0.1),
    TestCase(test_simple_exchange, "chat_unreliable_013", "Send message to other user and expect success (with the drop 0.1, delay from 0 to 1 seconds, and bursts from 1 up to 16 bits)", ['RT1', 'RI1', 'RT7', 'RD1', 'RD3', 'RD5', 'RE1', 'RE2', 'RE3'], drop=0.1, burst=0.05, burstLenLower=1, burstLenUpper=16, delay=1, delayLenLower=0, delayLenUpper=1),
    TestCase(test_exchange_with_multiple, "chat_unreliable_014", "Sending multiple messages to multiple clients and checking the message ordering (with delay from 0 to 3 seconds)", ['RT1', 'RI1', 'RT7', 'RA2', 'RD1', 'RD2', 'RD3', 'RD4'], delay=1, delayLenLower=0, delayLenUpper=3),
    TestCase(test_exchange_with_multiple, "chat_unreliable_015", "Sending multiple messages to multiple clients and checking the message ordering (with the drop 0.1, delay from 0 to 1 seconds, and bursts from 1 up to 16 bits)", ['RT1', 'RI1', 'RT7', 'RD1', 'RD3', 'RD5', 'RE1', 'RE2', 'RE3'], drop=0.1, burst=0.05, burstLenLower=1, burstLenUpper=16, delay=1, delayLenLower=0, delayLenUpper=1),
]


parser = argparse.ArgumentParser(description='Process test arguments')

parser.add_argument('--case', type=str, help='Test case name', default=None)
parser.add_argument('--tags', type=str, help='List of tags', default=None)
parser.add_argument('--disablecolors', type=str, help='(optional) for codegrade to disable colors for readable output', default=None)
args = parser.parse_args()

case = args.case
disable_colors = args.disablecolors

if args.tags:
    try:
        # Assuming the tags are passed in a format that's convertible to a Python list
        tags_list = json.loads(args.tags.replace("'", "\""))
    except json.JSONDecodeError as e:
        print(f"Error parsing tags: {e}")
        tags_list = None
else:
    tags_list = None

def execute_tests(test_cases, case, tags_list):
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

if not execute_tests(test_cases=test_cases, case=case, tags_list=tags_list):
    exit(1)
else:
    exit(0)
