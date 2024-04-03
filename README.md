# Automated Testing

### Overview

For this lab, we provide and encourage you to actively use tests during the development process. Why? While tests **do not guarantee** that your submission will be accepted by your TA, they provide you with immediate and actionable feedback on your developments.

We have tests available for the following assignments:

1. Chat Client
2. Chat Server
3. Chat For Unreliable Networks
4. HTTP Server
5. DNS Server

Tests can be both executed locally and on CodeGrade. Please note, that for submission purposes, only the CodeGrade version counts. That is if you have tests passing locally but not on CodeGrade your assignment **will not** be accepted.

### How to Use?

For this course, we distribute you the full test code which is identical to the one used on CodeGrade. You are allowed to execute the tests locally and, if you cannot pass one test, we encourage you to look into the test code and modify it to figure out what exactly does not work in your program. Please note; however, that for submission purposes, only the CodeGrade tests count (and those you cannot modify). You are also allowed to not use the local tests but use exclusively CodeGrade tests. However, this is not a recommended approach as it will make the coding harder.

### How to Start Tests Locally?

To run the tests locally, you need to install Docker first. The installation instructions can be found [here](https://docs.docker.com/engine/install/).

To emulate the Docker environment we provide you with the Docker image. You can build this image with the command.

<pre class="language-bash"><code class="lang-bash"><strong>docker build -t compnet [FILE_PATH_TO_THE_DOCKER_FOLDER]
</strong></code></pre>

If your present working directory is the same as the one where the Dockerfile is in then you can use a command.

```bash
docker build -t compnet .
```

To start the docker container run:

```bash
docker run --network="host" -v .:/home/compnet -it compnet
```

Please note, that this command will mount your current folder onto the docker container; thus, before executing the command, please make sure your present working directory is the root directory of the tests template.

Navigate to the respective assignment folder, put your implementation in the respective file (please note tests will not work if your implementation is in a file other than the dedicated for implementation one), and run:

```bash
python3 check.py
```

This command will execute all test cases showing whether your code passes those. Our tests support both executing a single test by its respective ID and executing tests by tagging. Tags have a one-to-one mapping with the requirements listed in the requirement section of every coding assignment. Tags have two main use cases: reverse engineer which functionality part is not working when seeing a failed test or partially test your program on already developed functionality.

To execute a single test by its tag run:

```bash
python3 check.py --case "case_name"
```

For example, if you want to run only one case `chat_client_001` then run:

```bash
python3 check.py --case "chat_client_001"
```

To execute all the tests with a set of tags you can make use of `--tags` an argument where you should pass your arguments as a JSON string.

```bash
python3 check.py --tags '["TAG1", "TAG2"...]'
```

For example, if you want to execute all the tests that have either tag `R1` or `R2`, then run:

```bash
python3 check.py --tags '["R1", "R2"]'
```

Please note, that if you specify a test case, the tags argument will be disregarded.

### Recommended Approach

1. Implement some part of your assignment functionality.
2. Test that your part is working correctly. You should use `--tags` or `--case` arguments to isolate the tests you wish to run.
3. If the functionality is not working, debug your code by looking at the output logs, emulating the test case manually, or modifying the tests.
4. When you have successfully debugged your feature move on to the next one and iterate the process until all assignment requirements are satisfied.

### Unrecommended Approach (but one that is possible)

1. Implement your assignment functionality in one go.
2. Test your functionality and debug the code until the program fulfills all the assignment requirements.

Why is it unrecommended? All the tests are built on top of one another and if your program fails one of the "base" tests, you will fail all the tests that are built on top of that test. Due to the fact that testing was not used throughout the development process, there is a bigger search space for a bug - it could be anywhere in your code.

### Bug Bounty Program

While we worked hard on the tests, but, as in the case with all the software, there can be bugs. Have you found one? Great! Submit your fix through a GitHub pull request and earn up to 50 points and a CVable achievement! You can always simply let us know about a bug you found and we will fix it; however, in this case, you do not get any points. Please note, that we reserve a right to reject your PR based on the styling or any other (we find applicable) issues.
