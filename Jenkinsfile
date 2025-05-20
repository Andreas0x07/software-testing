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
                // This checkout step in the Jenkinsfile ensures the correct branch is used for the build,
                // overriding any default SCM polling behavior if necessary.
                // It will use the SCM configuration from the Jenkins job (URL, credentials).
                // We specify the branch explicitly.
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/lab78']], // Ensure this matches your branch
                    userRemoteConfigs: scm.userRemoteConfigs, // Uses credentials from job config
                    extensions: scm.extensions // Includes any SCM extensions from job config
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
                    echo "Chromium Driver: $(which chromium-driver || echo 'chromium-driver not found')"
                    echo "Chromium: $(which chromium || echo 'chromium not found')"
                    echo "Checking sudo access for jenkins user:"
                    sudo -n true && echo "Jenkins user has passwordless sudo access." || echo "Jenkins user does NOT have passwordless sudo access (or sudo not found)."

                    echo "Creating Python virtual environment..."
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    
                    echo "Installing/Verifying Python packages..."
                    pip install --upgrade pip
                    pip install pytest requests selenium selenium-wire locust psutil HtmlTestRunner

                    echo "Python virtual environment setup complete."
                '''
            }
        }

        stage('Prepare OpenBMC Image') {
            steps {
                sh '''
                    echo "Downloading OpenBMC Romulus image..."
                    wget -nv "${env.OPENBMC_IMAGE_URL}" -O romulus.zip
                    
                    echo "Unzipping Romulus image..."
                    unzip -o romulus.zip -d .
                    
                    echo "Contents of romulus directory:"
                    ls -l romulus/
                    
                    if [ ! -f romulus/*.static.mtd ]; then
                        echo "ERROR: No .static.mtd file found in romulus directory after unzip."
                        find . -name '*.static.mtd' -print
                        exit 1
                    fi
                    echo "OpenBMC image prepared."
                '''
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                sh '''
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

                    echo "Finding OpenBMC MTD image file..."
                    OPENBMC_IMAGE_FILE=$(find romulus -name '*.static.mtd' -print -quit)
                    
                    if [ -z "${OPENBMC_IMAGE_FILE}" ]; then
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
                    echo "Nohup QEMU process started with PID ${QEMU_NOHUP_PID}."
                    sleep 5 
                    QEMU_ACTUAL_PID=$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}")
                    
                    if [ -z "${QEMU_ACTUAL_PID}" ]; then
                        echo "Failed to get QEMU actual PID. Log content:"
                        cat qemu_openbmc.log
                        # Attempt to kill the nohup job if the main process didn't start
                        sudo kill -9 ${QEMU_NOHUP_PID} || echo "Failed to kill nohup PID ${QEMU_NOHUP_PID}"
                        exit 1
                    fi
                    echo "QEMU started with actual PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                    echo ${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE}

                    echo "Waiting for OpenBMC to boot (90 seconds)..."
                    sleep 90
                    
                    echo "Verifying OpenBMC IPMI responsiveness..."
                    # Increased timeout for ipmitool, default is too short for QEMU sometimes
                    ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc -R 3 -N 5 chassis power status
                    if [ $? -ne 0 ]; then
                        echo "OpenBMC did not start correctly or is not responding via IPMI."
                        echo "QEMU Log (qemu_openbmc.log):"
                        cat qemu_openbmc.log
                        if [ -f ${QEMU_PID_FILE} ]; then
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
                    # Assuming test_redfish.py is at the root of your repository
                    cp test_redfish.py tests/api/ 
                    pytest tests/api/test_redfish.py --junitxml=pytest_api_report.xml || echo "PyTest API tests failed or found issues."
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
                    # Assuming openbmc_auth_tests.py is at the root of your repository
                    cp openbmc_auth_tests.py tests/webui/
                    echo "Running WebUI tests..."
                    # Ensure reports directory exists for HtmlTestRunner
                    mkdir -p reports 
                    python tests/webui/openbmc_auth_tests.py || echo "Selenium WebUI tests failed or found issues."
                '''
            }
            post {
                always {
                    // HtmlTestRunner output is named 'test_report.html' at the root of workspace by your script
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
                    # Assuming locustfile.py is at the root of your repository
                    cp locustfile.py tests/load/
                    echo "Starting Locust load test..."
                    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html || echo "Locust load test execution had issues or completed with non-zero exit."
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
