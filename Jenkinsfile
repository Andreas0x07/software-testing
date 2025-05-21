// Jenkinsfile
pipeline {
    agent any
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid'
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
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
                sh '''
                    echo "Running in custom Docker agent. System packages should be pre-installed."
                    echo "Verifying key installations..."
                    echo "Git version: $(git --version || echo 'git not found')"
                    echo "QEMU: $(which qemu-system-arm || echo 'qemu-system-arm not found')"
                    echo "Python3: $(which python3 || echo 'python3 not found')"
                    echo "pip3: $(which pip3 || echo 'pip3 not found')"
                    echo "IPMItool: $(which ipmitool || echo 'ipmitool not found')"
                    echo "Chromium Driver: $(which chromedriver || which chromium-driver || echo 'chromium-driver not found')"
                    echo "Chromium: $(which chromium || echo 'chromium not found')"
                    echo "Checking sudo access for jenkins user:"
                    sudo -n true && echo "Jenkins user has passwordless sudo access." || echo "Jenkins user does NOT have passwordless sudo access (or sudo not found)."
                    echo "Creating Python virtual environment..."
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    
                    echo "Installing/Verifying Python packages..."
                    pip install --upgrade pip
                    pip install pytest requests selenium selenium-wire locust psutil html-testRunner blinker==1.7.0

                    echo "Python virtual environment setup complete."
                '''
            }
        }

        stage('Prepare OpenBMC Image') {
            steps {
                sh '''
                    echo "Downloading OpenBMC Romulus image..."
                    wget -nv "${OPENBMC_IMAGE_URL}" -O romulus.zip
                    
                    echo "Unzipping Romulus image..."
                    unzip -o romulus.zip -d .
                    echo "Contents of romulus directory:"
                    ls -l romulus/
                    
                    OPENBMC_MTD_CHECK=$(find romulus -name '*.static.mtd' -print -quit)
                    if [ -z "${OPENBMC_MTD_CHECK}" ] || [ ! -f "${OPENBMC_MTD_CHECK}" ]; then
                        echo "ERROR: No .static.mtd file found in romulus directory after unzip."
                        echo "Listing current directory structure:"
                        ls -R .
                        exit 1
                    fi
                    echo "OpenBMC image prepared: ${OPENBMC_MTD_CHECK}"
                '''
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                sh '''
                    set +e 
                    
                    if pgrep -f "qemu-system-arm -M romulus-bmc";
                    then
                        echo "QEMU already running. Attempting to kill..."
                        sudo pkill -f "qemu-system-arm -M romulus-bmc"
                        sleep 5
                
                        if pgrep -f "qemu-system-arm -M romulus-bmc";
                        then
                            echo "Failed to kill existing QEMU. Exiting."
                            exit 1
                        fi
                    fi

                    echo "Finding OpenBMC MTD image file..."
                    OPENBMC_IMAGE_FILE=$(find romulus -name '*.static.mtd' -print -quit)
                    
                    if [ -z "${OPENBMC_IMAGE_FILE}" ];
                    then
                        echo "ERROR: OpenBMC MTD image file not found in romulus/ directory."
                        exit 1
                    fi
                    echo "Using MTD image: ${OPENBMC_IMAGE_FILE}"

                    echo "Starting QEMU with OpenBMC..."
                    nohup qemu-system-arm \\
                        -m 256 \\
                        -M romulus-bmc \\
                        -nographic \\
                        -drive file=${OPENBMC_IMAGE_FILE},format=raw,if=mtd \\
                        -net nic \\
                        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                        > qemu_openbmc.log 2>&1 &
                    
                    QEMU_NOHUP_PID=$!
                    echo "Nohup QEMU process potentially started with PID ${QEMU_NOHUP_PID}."
                    
                    sleep 8 
                    
                    QEMU_ACTUAL_PID=""
                    if ps -p ${QEMU_NOHUP_PID} > /dev/null;
                    then
                        echo "Process with PID ${QEMU_NOHUP_PID} (from nohup) is running."
                        ACTUAL_CMD=$(ps -o args= -p ${QEMU_NOHUP_PID})
                        echo "Command for PID ${QEMU_NOHUP_PID}: ${ACTUAL_CMD}"
                        
                        if echo "${ACTUAL_CMD}" | grep -q "qemu-system-arm" && \
                           echo "${ACTUAL_CMD}" | grep -q -- "-M romulus-bmc" && \
                           echo "${ACTUAL_CMD}" | grep -q -- "-nographic" && \
                           echo "${ACTUAL_CMD}" | grep -q -- "-drive.*${OPENBMC_IMAGE_FILE}"; then
                            echo "Command for PID ${QEMU_NOHUP_PID} matches expected QEMU process."
                            QEMU_ACTUAL_PID=${QEMU_NOHUP_PID}
                        else
                            echo "Command for PID ${QEMU_NOHUP_PID} (${ACTUAL_CMD}) does NOT precisely match all expected QEMU parameters."
                            echo "Expected to contain: 'qemu-system-arm', '-M romulus-bmc', '-nographic', AND '-drive containing ${OPENBMC_IMAGE_FILE}'"
                        fi
                    else
                        echo "Process with PID ${QEMU_NOHUP_PID} (from nohup) is NOT running after sleep."
                    fi

                    if [ -z "${QEMU_ACTUAL_PID}" ];
                    then
                        echo "Failed to confirm QEMU process using PID from nohup (${QEMU_NOHUP_PID})."
                        echo "QEMU Log (qemu_openbmc.log) content:"
                        cat qemu_openbmc.log
                        echo "Listing current qemu processes (if any) via ps:"
                        ps aux | grep qemu-system-arm | grep -v grep
                        
                        if ps -p ${QEMU_NOHUP_PID} > /dev/null;
                        then
                           echo "Killing unverified/mismatched process with PID ${QEMU_NOHUP_PID}."
                           sudo kill -9 ${QEMU_NOHUP_PID} || echo "Failed to kill PID ${QEMU_NOHUP_PID}, or it was not running."
                        fi
                        exit 1
                    fi
                    
                    echo "QEMU confirmed running with PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                    echo ${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE}

                    echo "Waiting for OpenBMC to boot (150 seconds initial wait)..." # Increased wait time
                    sleep 150
                    
                    echo "Verifying OpenBMC IPMI responsiveness with retries..."
                    RETRY_COUNT=0
                    MAX_RETRIES=5 # Try up to 5 times (total additional wait up to 4*15 = 60 seconds)
                    IPMI_SUCCESS=0
                    while [ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]; do
                        echo "IPMI check attempt $((RETRY_COUNT + 1)) of ${MAX_RETRIES}..."
                        ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc -R 5 -N 10 chassis power status
                        if [ $? -eq 0 ]; then
                            IPMI_SUCCESS=1
                            echo "IPMI check successful."
                            break
                        fi
                        RETRY_COUNT=$((RETRY_COUNT + 1))
                        if [ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]; then
                            echo "IPMI check failed. Retrying in 15 seconds..."
                            sleep 15
                        else
                            echo "IPMI check failed on final attempt."
                        fi
                    done

                    if [ ${IPMI_SUCCESS} -ne 1 ]; then
                        echo "OpenBMC did not start correctly or is not responding via IPMI after ${MAX_RETRIES} attempts."
                        echo "QEMU Log (qemu_openbmc.log):"
                        cat qemu_openbmc.log
                        if [ -f ${QEMU_PID_FILE} ];
                        then
                            echo "Attempting to kill QEMU PID $(cat ${QEMU_PID_FILE})..."
                            sudo kill -9 $(cat ${QEMU_PID_FILE}) || echo "Failed to kill QEMU PID $(cat ${QEMU_PID_FILE}), or it wasn't running."
                        else
                             sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                        fi
                        exit 1
                    fi
                    echo "OpenBMC seems to be running."
                    set -e
                '''
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/api 
                    cp test_redfish.py tests/api/ 
                    pytest tests/api/test_redfish.py --junitxml=pytest_api_report.xml
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'pytest_api_report.xml, qemu_openbmc.log', fingerprint: true
                    junit 'pytest_api_report.xml'
                }
            }
        }

        stage('Run WebUI Autotests (Selenium)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/webui
                    cp openbmc_auth_tests.py tests/webui/
                    echo "Running WebUI tests..."
                    python tests/webui/openbmc_auth_tests.py
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_report.html, qemu_openbmc.log', fingerprint: true
                    publishHTML([allowMissing: true, alwaysLinkToLastBuild: false, keepAll: true, reportDir: '.', reportFiles: 'test_report.html', reportName: 'Selenium WebUI Report', reportTitles: ''])
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/load
                    cp locustfile.py tests/load/
                    echo "Starting Locust load test..."
                    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'locust_report_stats.csv, locust_report_stats_history.csv, locust_report.html, qemu_openbmc.log', fingerprint: true
                    publishHTML([allowMissing: true, alwaysLinkToLastBuild: false, keepAll: true, reportDir: '.', reportFiles: 'locust_report.html', reportName: 'Locust Load Test Report', reportTitles: ''])
                }
            }
        }
    }

    post {
        always {
            script {
                sh '''
                    echo "Pipeline finished. Cleaning up QEMU..."
                    if [ -f ${QEMU_PID_FILE} ]; then
                        QEMU_PID_TO_KILL=$(cat ${QEMU_PID_FILE})
                        if [ -n "${QEMU_PID_TO_KILL}" ]; then
                            echo "Attempting to kill QEMU process with PID ${QEMU_PID_TO_KILL}..."
                            sudo kill -9 ${QEMU_PID_TO_KILL} || echo "Failed to kill QEMU PID ${QEMU_PID_TO_KILL}, or it wasn't running."
                        else
                            echo "No QEMU PID found in ${QEMU_PID_FILE}. Searching by process name..."
                            sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                        fi
                    else
                        echo "QEMU PID file (${QEMU_PID_FILE}) not found. Searching by process name..."
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                    fi
                    echo "Cleanup attempt finished."
                '''
            }
        }
    }
}
