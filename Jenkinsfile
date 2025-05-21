// Jenkinsfile
pipeline {
    agent any
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid'
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
        REPORTS_DIR = 'reports'
    }

    stages {
        stage('Checkout SCM') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/lab78']],
                    userRemoteConfigs: scm.userRemoteConfigs,
                    extensions: scm.extensions
                ])
                sh 'ls -la'
            }
        }

        stage('Setup Environment') {
            steps {
                sh """
                    echo "Running in Docker agent: ${env.JENKINS_AGENT_NAME:-master}"
                    echo "Verifying key system installations..."
                    echo "Git version: \$(git --version || echo 'git not found')"
                    echo "QEMU: \$(which qemu-system-arm || echo 'qemu-system-arm not found')"
                    echo "Python3: \$(which python3 || echo 'python3 not found')"
                    echo "pip3: \$(which pip3 || echo 'pip3 not found')"
                    echo "IPMItool: \$(which ipmitool || echo 'ipmitool not found')"
                    echo "Chromium Driver: \$(which chromedriver || echo 'chromedriver not found')"
                    echo "Chromium: \$(which chromium || echo 'chromium not found')"
                    sudo -n true && echo "Jenkins user has passwordless sudo access." || echo "Jenkins user does NOT have passwordless sudo access."

                    echo "Creating Python virtual environment '${PYTHON_VENV}'..."
                    python3 -m venv ${WORKSPACE}/${PYTHON_VENV}

                    echo "Installing/Verifying Python packages into venv..."
                    ${WORKSPACE}/${PYTHON_VENV}/bin/pip install --upgrade pip
                    ${WORKSPACE}/${PYTHON_VENV}/bin/pip install pytest requests selenium selenium-wire locust psutil html-testRunner blinker==1.7.0

                    echo "Python virtual environment setup complete."
                    echo "Making reports directory: ${REPORTS_DIR}"
                    mkdir -p ${REPORTS_DIR}
                """
            }
        }

        stage('Prepare OpenBMC Image') {
            steps {
                sh """
                    echo "Downloading OpenBMC Romulus image..."
                    wget -nv "${OPENBMC_IMAGE_URL}" -O romulus.zip

                    echo "Unzipping Romulus image..."
                    unzip -o romulus.zip -d .
                    echo "Contents of romulus directory:"
                    ls -l romulus/

                    OPENBMC_MTD_CHECK=\$(find romulus -name '*.static.mtd' -print -quit)
                    if [ -z "\${OPENBMC_MTD_CHECK}" ] || [ ! -f "\${OPENBMC_MTD_CHECK}" ]; then
                        echo "ERROR: No .static.mtd file found in romulus directory after unzip."
                        echo "Listing current directory structure:"
                        ls -R .
                        exit 1
                    fi
                    echo "OpenBMC image prepared: \${OPENBMC_MTD_CHECK}"
                """
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                sh """
                    set +e 
                    if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                        echo "QEMU already running. Attempting to kill..."
                        sudo pkill -f "qemu-system-arm -M romulus-bmc"
                        sleep 5
                        if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                            echo "Failed to kill existing QEMU. Exiting."
                            exit 1
                        fi
                    fi
                    set -e

                    echo "Finding OpenBMC MTD image file..."
                    OPENBMC_IMAGE_FILE=\$(find romulus -name '*.static.mtd' -print -quit)
                    
                    if [ -z "\${OPENBMC_IMAGE_FILE}" ]; then
                        echo "ERROR: OpenBMC MTD image file not found in romulus/ directory."
                        exit 1
                    fi
                    echo "Using MTD image: \${OPENBMC_IMAGE_FILE}"

                    echo "Starting QEMU with OpenBMC..."
                    nohup qemu-system-arm \\
                        -m 256 \\
                        -M romulus-bmc \\
                        -nographic \\
                        -drive file=\${OPENBMC_IMAGE_FILE},format=raw,if=mtd \\
                        -net nic \\
                        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                        > qemu_openbmc.log 2>&1 &
                    
                    QEMU_NOHUP_PID=\$!
                    echo "Nohup QEMU process potentially started with PID \${QEMU_NOHUP_PID}."
                    
                    sleep 15 
                    
                    QEMU_ACTUAL_PID=""
                    if ps -p \${QEMU_NOHUP_PID} > /dev/null; then
                        echo "Process with PID \${QEMU_NOHUP_PID} (from nohup) is running."
                        ACTUAL_CMD=\$(ps -o args= -p \${QEMU_NOHUP_PID})
                        echo "Command for PID \${QEMU_NOHUP_PID}: \${ACTUAL_CMD}"
                        
                        # Simplified check: just ensure it's a qemu-system-arm command
                        if echo "\${ACTUAL_CMD}" | grep -q "qemu-system-arm" && echo "\${ACTUAL_CMD}" | grep -q -- "-M romulus-bmc"; then
                            echo "Command for PID \${QEMU_NOHUP_PID} matches expected QEMU process."
                            QEMU_ACTUAL_PID=\${QEMU_NOHUP_PID}
                        else
                            echo "Command for PID \${QEMU_NOHUP_PID} (\${ACTUAL_CMD}) does NOT sufficiently match expected QEMU parameters."
                        fi
                    else
                        echo "Process with PID \${QEMU_NOHUP_PID} (from nohup) is NOT running after sleep."
                    fi

                    if [ -z "\${QEMU_ACTUAL_PID}" ]; then
                        echo "Failed to confirm QEMU process using PID from nohup (\${QEMU_NOHUP_PID})."
                        echo "Attempting to find QEMU PID via pgrep..."
                        QEMU_ACTUAL_PID=\$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=\${OPENBMC_IMAGE_FILE}")
                        if [ -z "\${QEMU_ACTUAL_PID}" ]; then
                             echo "Still failed to find QEMU PID via pgrep."
                             echo "QEMU Log (qemu_openbmc.log) content:"
                             cat qemu_openbmc.log || echo "qemu_openbmc.log not found or empty."
                             echo "Listing current qemu processes (if any) via ps:"
                             ps aux | grep qemu-system-arm | grep -v grep
                             exit 1
                        else
                            echo "Found QEMU PID \${QEMU_ACTUAL_PID} using pgrep."
                        fi
                    fi
                    
                    echo "QEMU confirmed running with PID \${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                    echo \${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE}

                    echo "Waiting for OpenBMC to boot (90 seconds)..."
                    sleep 90
                    
                    echo "Verifying OpenBMC IPMI responsiveness..."
                    ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc -R 3 -N 5 chassis power status
                    if [ \$? -ne 0 ]; then
                        echo "OpenBMC did not start correctly or is not responding via IPMI."
                        echo "QEMU Log (qemu_openbmc.log):"
                        cat qemu_openbmc.log || echo "qemu_openbmc.log not found or empty."
                        if [ -f ${QEMU_PID_FILE} ]; then
                            echo "Attempting to kill QEMU PID \$(cat ${QEMU_PID_FILE})..."
                            sudo kill -9 \$(cat ${QEMU_PID_FILE}) || echo "Failed to kill QEMU PID, or it wasn't running."
                        else
                             sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                        fi
                        exit 1
                    fi
                    echo "OpenBMC seems to be running."
                """
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh """
                    echo "Activating Python venv and running PyTest..."
                    . ${WORKSPACE}/${PYTHON_VENV}/bin/activate
                    
                    mkdir -p tests/api
                    cp test_redfish.py tests/api/
                    
                    echo "Running PyTest tests..."
                    ${WORKSPACE}/${PYTHON_VENV}/bin/pytest tests/api/test_redfish.py --junitxml=${REPORTS_DIR}/pytest_api_report.xml
                    
                    if [ ! -f "${REPORTS_DIR}/pytest_api_report.xml" ]; then
                        echo "ERROR: PyTest report ${REPORTS_DIR}/pytest_api_report.xml not found after test execution."
                        exit 1
                    fi
                    echo "PyTest execution finished."
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/pytest_api_report.xml, qemu_openbmc.log", fingerprint: true, allowEmptyArchive: true
                    junit testResults: "${REPORTS_DIR}/pytest_api_report.xml", allowEmptyResults: true
                }
            }
        }

        stage('Run WebUI Autotests (Selenium)') {
            steps {
                sh """
                    echo "Activating Python venv and running Selenium WebUI tests..."
                    . ${WORKSPACE}/${PYTHON_VENV}/bin/activate

                    mkdir -p tests/webui
                    cp openbmc_auth_tests.py tests/webui/
                    
                    echo "Running Selenium WebUI tests..."
                    ${WORKSPACE}/${PYTHON_VENV}/bin/python tests/webui/openbmc_auth_tests.py
                    
                    if [ ! -f "${REPORTS_DIR}/selenium_webui_report.html" ]; then
                        echo "ERROR: Selenium report ${REPORTS_DIR}/selenium_webui_report.html not found after test execution."
                        # exit 1 # Commenting out exit 1 to see if HTML publisher still picks it up if path is correct
                    fi
                    echo "Selenium WebUI tests finished."
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/selenium_webui_report.html, qemu_openbmc.log", fingerprint: true, allowEmptyArchive: true
                    publishHTML([
                        allowMissing: true, 
                        alwaysLinkToLastBuild: false, 
                        keepAll: true, 
                        reportDir: "${REPORTS_DIR}", 
                        reportFiles: 'selenium_webui_report.html', 
                        reportName: 'Selenium WebUI Report', 
                        reportTitles: ''
                    ])
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh """
                    echo "Activating Python venv and running Locust load tests..."
                    . ${WORKSPACE}/${PYTHON_VENV}/bin/activate
                    
                    mkdir -p tests/load
                    cp locustfile.py tests/load/
                    
                    echo "Starting Locust load test..."
                    ${WORKSPACE}/${PYTHON_VENV}/bin/locust -f tests/load/locustfile.py \\
                        --headless -u 10 -r 2 -t 30s \\
                        --host=https://localhost:2443 \\
                        --csv=${REPORTS_DIR}/locust_report \\
                        --html=${REPORTS_DIR}/locust_report.html
                    
                    if [ ! -f "${REPORTS_DIR}/locust_report.html" ]; then
                        echo "ERROR: Locust HTML report ${REPORTS_DIR}/locust_report.html not found after test execution."
                        # exit 1
                    fi
                    echo "Locust load testing finished."
                """
            }
            post {
                always {
                    archiveArtifacts artifacts: "${REPORTS_DIR}/locust_report_stats.csv, ${REPORTS_DIR}/locust_report_stats_history.csv, ${REports_DIR}/locust_report_failures.csv, ${REPORTS_DIR}/locust_report.html, qemu_openbmc.log", fingerprint: true, allowEmptyArchive: true
                    publishHTML([
                        allowMissing: true, 
                        alwaysLinkToLastBuild: false, 
                        keepAll: true, 
                        reportDir: "${REPORTS_DIR}", 
                        reportFiles: 'locust_report.html', 
                        reportName: 'Locust Load Test Report', 
                        reportTitles: ''
                    ])
                }
            }
        }
    }

    post {
        always {
            script {
                sh """
                    echo "Pipeline finished. Cleaning up QEMU..."
                    if [ -f ${QEMU_PID_FILE} ]; then
                        QEMU_PID_TO_KILL=\$(cat ${QEMU_PID_FILE})
                        if [ -n "\${QEMU_PID_TO_KILL}" ] && ps -p \${QEMU_PID_TO_KILL} > /dev/null; then
                            echo "Attempting to kill QEMU process with PID \${QEMU_PID_TO_KILL}..."
                            sudo kill -9 \${QEMU_PID_TO_KILL} || echo "Failed to kill QEMU PID \${QEMU_PID_TO_KILL}, or it wasn't running."
                            rm -f ${QEMU_PID_FILE}
                        else
                            echo "No valid QEMU PID found in ${QEMU_PID_FILE} or process not running. Searching by process name..."
                            sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill attempt: QEMU process not found or already stopped."
                        fi
                    else
                        echo "QEMU PID file (${QEMU_PID_FILE}) not found. Searching by process name..."
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill attempt: QEMU process not found or already stopped."
                    fi
                    echo "Cleanup attempt finished."
                """
            }
        }
    }
}
