import pexpect
import http.client
import argparse
import json
import random
import string
import socket
import requests
import re
from pexpect.exceptions import TIMEOUT as TimeoutException, EOF as EndOfFileException
from bs4 import BeautifulSoup

SERVER_ADDRESS = "127.0.0.1"
SERVER_PORT = 8000
STUDENT_FILE_PATH = "../student/http_server_check/server.py"

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

        for process in processes_to_terminate:
            process.terminate(force=True)

        raise TestException(f'unexpected output at step {step}!\nExpected output:\n\n{expect_string}\n\nActual output: \n\n{child_process.before}\n\nTotal program output:\n\n{output_buffer}')
    except EndOfFileException:
        output_buffer += child_process.before + child_process.after

        for process in processes_to_terminate:
            process.terminate(force=True)
            
        raise TestException(f'program has unexpectidly terminated at step {step}!\nExpected output:\n\n{expect_string}\n\nProgram\'s last output: \n\n{child_process.before}\n\nTotal program output:\n\n{output_buffer}')
    
    return output_buffer

def handle_httpconnection_request(page_path, method="GET", timeout=3):
    try:
        connection = http.client.HTTPConnection(SERVER_ADDRESS, SERVER_PORT, timeout=timeout)
        connection.request(method, page_path)

        response = connection.getresponse()

        return response
    
    except socket.timeout:
        raise TestException(f'timeout when requesting {page_path} with method {method}')
    except Exception as e:
        raise TestException(f'error when requesting {page_path} with method {method}: {e}')
    
def handle_requests_request(page_path, data):
    try:
        response = requests.post(f'http://{SERVER_ADDRESS}:{SERVER_PORT}{page_path}', data=data, timeout=(5, 5))
        return response
    except requests.exceptions.Timeout:
        raise TestException(f'timeout when requesting {page_path} with method POST')
    except Exception as e:
        raise TestException(f'error when requesting {page_path} with method POST: {e}')

def start_server():
    server_process = execute_and_detach(f'python3 {STUDENT_FILE_PATH} --address {SERVER_ADDRESS} --port {SERVER_PORT}')
    EXPECTED_OUTPUT = f'Serving HTTP on port {SERVER_PORT}'

    output_buffer = handle_pexpect(server_process, [server_process], EXPECTED_OUTPUT, "", "starting a server")
        
    return server_process, output_buffer


def index_reachable():
    __, _ = start_server()
    PAGE_PATH = "/"

    response = handle_httpconnection_request(PAGE_PATH, "GET")

    if response.status != 200:
        raise TestException(f'status code when requesting {PAGE_PATH} code was expected to be 200 but was {response.status}')

def not_found_page_reachable():
    __, _ = start_server()
    PAGE_PATH = ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16)))
    
    response = handle_httpconnection_request(PAGE_PATH, "GET")

    if response.status != 404:
        raise TestException(f'status code when requesting {PAGE_PATH} expecteed to be 404 but was {response.status}')
    
def check_encoding():
    __, _ = start_server()
    PAGE_PATH = "/"

    response = handle_httpconnection_request(PAGE_PATH, "GET")
    content_type = response.getheader('Content-Type')

    match = re.search('charset=([^\s;]+)', content_type, re.I)

    if not match:
        raise TestException('The encoding must be specified')
    
    elif match.group(1).lower() != 'utf-8':
        raise TestException(f'encoding expected utf-8 but was {match.group(1).lower()}')
    
def check_content_length():
    __, _ = start_server()

    PAGE_PATH = "/"
    response = handle_httpconnection_request(PAGE_PATH, "GET")

    content_length_header = response.getheader('Content-Length')
    if content_length_header is None:
        raise TestException("content-length must be specified")
    
    content_length = int(content_length_header)

    content = response.read()
    actual_content_length = len(content)

    if content_length != actual_content_length:
        raise TestException(f'the content length specified {content_length} is not the actual content length {actual_content_length}')


def load_index_page_cat_images():
    __, _ = start_server()
    PAGE_PATH_1 = "/img/gleb_cat.jpeg"
    PAGE_PATH_2 = "/img/standing_cat.jpg"

    response = handle_httpconnection_request(PAGE_PATH_1, "GET")
    if response.status != 200:
        raise TestException(f'status code when requesting {PAGE_PATH_1} was expected to be 200 but was {response.status}.')

    response = handle_httpconnection_request(PAGE_PATH_2, "GET")
    if response.status != 200:
        raise TestException(f'status code when requesting {PAGE_PATH_2} was expected to be 200 but was {response.status}.')

def send_data():
    __, _ = start_server()
    PAGE_PATH = "/data"

    files = {
        'description': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
        'cat_url': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
    }

    response = requests.post(f'http://{SERVER_ADDRESS}:{SERVER_PORT}{PAGE_PATH}', data=files, timeout=(5, 5))

    if response.status_code != 201:
        raise TestException(f'status code when submitting form to {PAGE_PATH} was expected to be 201 but was {response.status_code}.')

    return files

def send_data_and_check_is_visible():
    __, _ = start_server()
    PAGE_PATH = "/data"

    files = {
        'description': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
        'cat_url': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
    }

    response = requests.post(f'http://{SERVER_ADDRESS}:{SERVER_PORT}{PAGE_PATH}', data=files, timeout=(5, 5))

    PATH = "/personal_cats.html"

    connection = http.client.HTTPConnection(SERVER_ADDRESS, SERVER_PORT, timeout=3)
    connection.request("GET", PATH)

    response = connection.getresponse()
    if response.status != 200:
        raise TestException(f'status code when requesting {PATH} was expected 200 but was {response.status} from expected 200.')
    
    html_content = response.read()
    soup = BeautifulSoup(html_content, 'lxml')

    cat_image = soup.find('img', src=files['cat_url'])

    if cat_image is None:
        raise TestException(f'could not find cat image after submitting a form!')

def test_persistent_connection():
    __, _ = start_server()
    
    PAGE_PATH_1 = "/"
    PAGE_PATH_2 = "/img/gleb_cat.jpeg"

    connection = http.client.HTTPConnection(SERVER_ADDRESS, SERVER_PORT, timeout=3)
    connection.request("GET", PAGE_PATH_1)

    try:
        response = connection.getresponse()
    except TimeoutException:
        raise TestException('timeout when requesting {PAGE_PATH_1} with method GET')

    response.read()
    if response.status != 200:
        raise TestException(f'status code when requesting {PAGE_PATH_1} was expected 200 but was {response.status}.')
    
    connection.request("GET", PAGE_PATH_2)

    try:
        response = connection.getresponse()
        response.read()
    except Exception as e:
        raise TestException(f'Error {e} when attempting to reuse HTTP connection. Make sure your server supports persistent HTTP1.1 connections')
    
    if response.status != 200:
        raise TestException(f'a response has different status code {response.status} from expected 200 when making a second request with the same connection.')
    
def check_index_is_visible():
    __, _ = start_server()

    PAGE_PATH = "/"
    response = handle_httpconnection_request(PAGE_PATH, "GET")

    content = response.read()

    soup = BeautifulSoup(content, 'html.parser')
    element = soup.find('span', id='test_hook_001')

    if element is None:
        raise TestException("could not find a test hook on an index page. Please check that the page is unmodified and visible")

def check_404_is_visible():
    __, _ = start_server()
    PAGE_PATH = ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16)))

    response = handle_httpconnection_request(PAGE_PATH, "GET")
    content = response.read()

    soup = BeautifulSoup(content, 'html.parser')
    element = soup.find('span', id='test_hook_003')

    if element is None:
        raise TestException("could not find a test hook on 404 page. Please check that the page is unmodified and visible")

def check_post_form_submission_is_visible():
    __, _ = start_server()
    data = {
        'description': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
        'cat_url': ''.join(random.choice(string.ascii_letters) for _ in range(random.randint(8, 16))),
    }

    response = handle_requests_request('/data', data)
    
    soup = BeautifulSoup(response.content, 'html.parser')
    element = soup.find('span', id='test_hook_002')

    if element is None:
        raise TestException("could not find a test hook on form response page. Please check that the page is unmodified and visible")
    
def check_form_emtpy_field_validation():
    __, _ = start_server()
    data = {
        'description': '',
        'cat_url': '',
    }

    response = handle_requests_request('/data', data)

    if response.status_code != 400:
        raise TestException(f'response has different status code {response.status_code} from expected 400 after submitting form with empty fields to test the validation')
    
def check_400_is_visible():
    __, _ = start_server()
    data = {
        'description': '',
        'cat_url': '',
    }

    response = handle_requests_request('/data', data)

    soup = BeautifulSoup(response.content, 'html.parser')
    element = soup.find('span', id='test_hook_004')

    if element is None:
        raise TestException("could not find a test hook on form 400 status code response page. Please check that the page is unmodified and visible")

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

class TestCase():
    def __init__(self, test_func, test_id, test_msg, tags=[]) -> None:
        self.tags = tags
        self.test_func = test_func
        self.test_id = test_id
        self.test_msg = test_msg
    
    def execute(self, disable_colors=False):
        success = True
        tags_string = ' '.join(self.tags)

        try:
            self.test_func()
            
            if not disable_colors:
                print(f'\033[92m[ \u2713 ] \033[30m{self.test_id}. {self.test_msg}. \033[92mSuccess! \033[0m')
            else:
                print(f'[ \u2713 ] {self.test_id}. {self.test_msg}. Success! ')

        except TypeError as e: # originates from pexpect .before if script terminates. except for more readable error message
            success = False
            
            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nYour server did not start \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nYour server did not start')
        
        except Exception as e:
            success = False

            if not disable_colors:
                print(f'\033[91m[ x ] \033[30m{self.test_id}. {self.test_msg} \033[91mFailed! \033[30m The list of tags is {tags_string} \nError message is {e} \033[0m')
            else:
                print(f'[ x ] {self.test_id}. {self.test_msg} Failed! The list of tags is {tags_string} \nError message is {e}')


        return success

test_cases = [
    TestCase(start_server, "http_server_001", "Start server and expect start up message", ['ISR1', 'ISR2']),
    TestCase(index_reachable, "http_server_002", "Request index page and expect 200 status code", ['PR1', 'PR2', 'RR1', 'RR4']),
    TestCase(check_encoding, "http_server_003", "Request a page and expect encoding utf-8", ['RR5']),
    TestCase(check_content_length, "http_server_004", "Request a page and expect appropiate content length", ['RR3']), 
    TestCase(not_found_page_reachable, "http_server_005", "Request non-existent page and expect 404 status code", ['RR7']),
    TestCase(load_index_page_cat_images, "http_server_006", "Request templated images and expect 200 status code", ['LR5']),
    TestCase(send_data, "http_server_007", "Submit form data to /data endpoint and expect 200 status code", ['LR7']),
    TestCase(send_data_and_check_is_visible, "http_server_008", "Submit form data to /data endpoint and expect form results appear on /personal_cats.html page", ['LR6', 'LR7']),
    TestCase(test_persistent_connection, "http_server_009", "Submit two requests using one connection and expect both success (testing server persistent connection support)", ['PR4']),
    TestCase(check_index_is_visible, "http_server_010", "Request index.html and expect to be visible", ['LR3']),
    TestCase(check_post_form_submission_is_visible, "http_server_011", "Submit form data to /data endpoint and expect page communication successull form submission visible", ['RR6']),
    TestCase(check_404_is_visible, "http_server_012", "Request non-existing page and expect 404 page to be visible", ['RR7']),
    TestCase(check_form_emtpy_field_validation, "http_server_013", "Submit empty form data to /data endpoint and expect 400 status code", ['RR8']),
    TestCase(check_400_is_visible, "http_server_014", "Submit empty form data to /data endpoint and expect 400 error page visible", ['RR8'])
]

parser = argparse.ArgumentParser(description='Process test arguments')

parser.add_argument('--case', type=str, help='Test case name', default=None)
parser.add_argument('--tags', type=str, help='List of tags', default=None)
parser.add_argument('--disablecolors', type=str, help='(optional) disable colors for the codegrade', default=False)
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
