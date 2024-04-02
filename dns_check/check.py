from pexpect.exceptions import TIMEOUT as TimeoutException, EOF as EndOfFileException
import json
import pexpect
import argparse
import time

SERVER_ADDRESS = '127.0.0.1'
IPV4ONLY = False

class TestException(Exception):
    pass

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

        raise TestException(f'unexpected output at step {step}!\nExpected output:\n\n{expect_string}\n\nActual output (the last printed line): \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    except EndOfFileException:
        output_buffer += child_process.before + child_process.after

        for process in processes_to_terminate:
            process.terminate(force=True)
            
        raise TestException(f'program has unexpectidly terminated at step {step}!\nExpected output:\n\n{expect_string}\n\nProgram\'s last printed line: \n\n{last_printed_line}\n\nTotal program output:\n\n{output_buffer}')
    
    return output_buffer

def start_server():
    return execute_and_detach(f'python3 dns.py --ipv4only {IPV4ONLY} --address {SERVER_ADDRESS} --port 8000')


def execute_and_detach(cmd):
    child = pexpect.spawn(cmd, encoding='utf-8')
    return child

def execute_and_wait(cmd):
    process = pexpect.spawn('/bin/sh', ['-c', cmd], encoding='utf-8')
    process.expect(pexpect.EOF)
    output = process.before  # Capture the output
    process.wait()

    return process.exitstatus, output

def test_simple():
    website_list = ['microsoft.com', 'google.com', 'vk.com', 'amazon.com', 'yahoo.com']

    for website in website_list:
        status_code, output = execute_and_wait(f'nslookup {website} {SERVER_ADDRESS}')

        if status_code != 0:
            raise TestException(f'error when fetching a website {website}. nslookup output is \n\n{output}')
        
def test_mx():
    website_list = ['microsoft.com', 'google.com', 'vk.com', 'amazon.com', 'yahoo.com']

    for website in website_list:
        status_code, output = execute_and_wait(f'nslookup -type=mx {website} {SERVER_ADDRESS}')

        if status_code != 0:
            raise TestException(f'error when fetching a website {website}.nslookup output is \n\n{output}')
        
def test_caching():
    website_list = ['microsoft.com', 'google.com', 'yahoo.com']
    
    for website in website_list:
        start_time_1 = time.time()
        status_code, output = execute_and_wait(f'nslookup {website} {SERVER_ADDRESS}:8000')
        finish_time_1 = time.time()

        time_difference_1 = finish_time_1 - start_time_1

        if status_code != 0:
            raise TestException(f'error when fetching a website {website} for the first time. nslookup output is \n\n{output}')
        
        start_time_2 = time.time()
        status_code, output = execute_and_wait(f'nslookup {website} {SERVER_ADDRESS}')
        finish_time_2 = time.time()

        time_difference_2 = finish_time_2 - start_time_2

        if status_code != 0:
            raise TestException(f'error when fetching a website {website} for the second time. nslookup output is \n\n{output}')
        

        if time_difference_2 >= time_difference_1:
            raise TestException(f'execution of first (uncached) request to fetch the address of {website} took as much or more time as the execution of second (cached) request. Make sure your server implements caching')

class TestCase():
    def __init__(self, test_func, test_id, test_msg, tags=[], max_clients=300) -> None:
        self.tags = tags
        self.test_func = test_func
        self.test_id = test_id
        self.test_msg = test_msg
        self.max_clients = max_clients
    
    def execute(self, disable_colors=False):
        success = True
        server_process = start_server()

        try:
            self.test_func()
            
            if not disable_colors:
                print(f'\033[92m[ \u2713 ] \033[30m{self.test_id}. {self.test_msg}. \033[92mSuccess! \033[30m')
            else:
                print(f'[ \u2713 ] {self.test_id}. {self.test_msg}. Success!')
        except Exception as e:
            tags_string = ' '.join(self.tags)
            try:
                server_process.expect(pexpect.EOF, timeout=0)
            except:
                pass

            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nError message is {e} \nThe server output is {server_process.before} \033[30m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nError message is {e} \nThe server output is {server_process.before}')
            
            success = False

            return success


test_cases = [
    TestCase(test_simple, "dns_001", "DNS with A and AAAA records", ['PR1', 'PR2', 'RR1', 'RR2', 'RR3', 'RR5']),
    TestCase(test_mx, "dns_002", "DNS with MX records", ['RR4', 'RR6']),
    TestCase(test_caching, "dns_003", "Server implements caching", ['CR1']),
]


parser = argparse.ArgumentParser(description='Process test arguments')

parser.add_argument('--case', type=str, help='Test case name', default=None)
parser.add_argument('--tags', type=str, help='List of tags', default=None)
parser.add_argument('--disablecolors', type=bool, help='(is used only for printing formatting in codegrade)', default=False)
parser.add_argument('--ipv4only', type=bool, help='mac setting as docker does not support ipv6 on mac', default=False)
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

if args.ipv4only:
    IPV4ONLY = True

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
