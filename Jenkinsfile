// Jenkinsfile
pipeline {
    agent any // Runs on any available agent/executor.
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid' // File to store QEMU PID, relative to workspace
        // Define the OpenBMC image URL here. This is from Lab 1 [cite: 4]
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
    }

    stages {
        // Stage to verify the initial checkout handled by Jenkins
        stage('Verify Workspace Content') {
            steps {
                sh 'echo "Workspace content after initial Jenkins SCM checkout:"'
                sh 'pwd' // Print current working directory (should be workspace)
                sh 'ls -la'
                sh 'echo "Current Git branch:"'
                sh 'git branch --show-current || git rev-parse --abbrev-ref HEAD' // Show current branch
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
                    echo "Checking sudo access for jenkins user:"
                    sudo -n true && echo "Jenkins user has passwordless sudo access." || echo "Jenkins user does NOT have passwordless sudo access (or sudo not found)."


                    echo "Creating Python virtual environment..."
                    python3 -m venv ${PYTHON_VENV} # Assuming PYTHON_VENV is defined in environment block
                    . ${PYTHON_VENV}/bin/activate
                    
                    echo "Installing/Verifying Python packages..."
                    pip install --upgrade pip
                    # These packages are for your tests, not system-wide tools
                    pip install pytest requests selenium selenium-wire locust psutil HtmlTestRunner #

                    echo "Python virtual environment setup complete."
                '''
            }
        }

        stage('Prepare OpenBMC Image') {
            steps {
                sh '''
                    echo "Downloading OpenBMC Romulus image..."
                    # Using wget from the previously defined environment variable [cite: 4]
                    wget "${OPENBMC_IMAGE_URL}" -O romulus.zip
                    
                    echo "Unzipping Romulus image..."
                    unzip -o romulus.zip -d . # Unzip to current directory, creating 'romulus' folder
                    
                    echo "Contents of romulus directory:"
                    ls -l romulus/
                    
                    # Check if MTD file exists [cite: 4]
                    if ! ls romulus/*.static.mtd 1> /dev/null 2>&1; then
                        echo "ERROR: No .static.mtd file found in romulus directory after unzip."
                        # Attempt to find it elsewhere if the structure is different
                        find . -name '*.static.mtd' -print
                        exit 1
                    fi
                    echo "OpenBMC image prepared."
                '''
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    sh '''
                        set +e # Don't exit immediately on error for this block
                        
                        echo "Finding OpenBMC MTD image file..."
                        # Find the MTD file within the 'romulus' directory [cite: 4]
                        OPENBMC_IMAGE_FILE=$(find romulus -name '*.static.mtd' -print -quit)
                        
                        if [ -z "${OPENBMC_IMAGE_FILE}" ]; then
                            echo "ERROR: OpenBMC MTD image file not found in romulus/ directory."
                            exit 1
                        fi
                        echo "Using MTD image: ${OPENBMC_IMAGE_FILE}"

                        echo "Checking for existing QEMU processes..."
                        # Using pgrep to find existing QEMU processes [cite: 179]
                        if pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}"; then
                            echo "QEMU already running with the same image. Attempting to kill..."
                            # Using pkill with sudo as it might be needed [cite: 208]
                            sudo pkill -9 -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}" || \
                            pkill -9 -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}" || \
                            echo "Failed to kill existing QEMU process. It might be run by another user or already stopped."
                            sleep 5 
                        fi

                        echo "Starting QEMU with OpenBMC..."
                        # QEMU command structure from Lab 1 [cite: 4]
                        nohup qemu-system-arm \\
                            -m 256 \\
                            -M romulus-bmc \\
                            -nographic \\
                            -drive file=${OPENBMC_IMAGE_FILE},format=raw,if=mtd \\
                            -net nic \\
                            -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                            > qemu_openbmc.log 2>&1 &
                        
                        echo $! > ${QEMU_PID_FILE} # Store PID of nohup
                        sleep 5 # Give QEMU a moment to actually start

                        QEMU_ACTUAL_PID=$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}")
                        
                        if [ -z "${QEMU_ACTUAL_PID}" ]; then
                            echo "Failed to get QEMU actual PID. Log content (qemu_openbmc.log):"
                            cat qemu_openbmc.log
                            exit 1
                        fi
                        echo "QEMU started with actual PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                        echo ${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE} # Overwrite with actual QEMU PID

                        echo "Waiting for OpenBMC to boot (60 seconds)..."
                        sleep 60 
                        
                        echo "Verifying OpenBMC IPMI responsiveness..."
                        # IPMI command from Lab 1 [cite: 5]
                        ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc chassis power status
                        if [ $? -ne 0 ]; then
                            echo "OpenBMC did not start correctly or is not responding via IPMI."
                            echo "QEMU Log (qemu_openbmc.log):"
                            cat qemu_openbmc.log
                            if [ -f ${QEMU_PID_FILE} ] && [ -s ${QEMU_PID_FILE} ]; then # Check if file exists and is not empty
                                PID_TO_KILL=$(cat ${QEMU_PID_FILE})
                                echo "Attempting to kill QEMU process ${PID_TO_KILL}..."
                                sudo kill -9 ${PID_TO_KILL} || kill -9 ${PID_TO_KILL} || echo "Failed to kill QEMU PID ${PID_TO_KILL}."
                            fi
                            exit 1
                        fi
                        echo "OpenBMC seems to be running."
                        set -e
                    '''
                }
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/api 
                    # Assuming test_redfish.py is at the root of your repo [cite: 147]
                    cp test_redfish.py tests/api/ 
                    pytest tests/api/test_redfish.py --junitxml=pytest_api_report.xml || echo "PyTest API tests completed (may have failures)."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'pytest_api_report.xml, qemu_openbmc.log', fingerprint: true // [cite: 191]
                    junit 'pytest_api_report.xml' // [cite: 192]
                }
            }
        }

        stage('Run WebUI Autotests (Selenium)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/webui
                    # Assuming openbmc_auth_tests.py is at the root of your repo [cite: 129]
                    cp openbmc_auth_tests.py tests/webui/
                    echo "Running WebUI tests..."
                    python tests/webui/openbmc_auth_tests.py || echo "Selenium WebUI tests completed (may have failures)."
                '''
            }
            post {
                always {
                    // The python script openbmc_auth_tests.py is configured to output 'test_report.html'
                    archiveArtifacts artifacts: 'test_report.html, qemu_openbmc.log', fingerprint: true
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    mkdir -p tests/load
                    # Assuming locustfile.py is at the root of your repo [cite: 167]
                    cp locustfile.py tests/load/
                    echo "Starting Locust load test..."
                    # Locust command from Lab 6 report/Jenkinsfile [cite: 161, 202]
                    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html || echo "Locust load test execution completed (may have issues)."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'locust_report_stats.csv, locust_report_stats_history.csv, locust_report.html, qemu_openbmc.log', fingerprint: true // [cite: 204]
                }
            }
        }
    }

    post {
        always {
            script {
                sh '''
                    echo "Pipeline finished. Cleaning up QEMU..."
                    if [ -f ${QEMU_PID_FILE} ] && [ -s ${QEMU_PID_FILE} ]; then # Check if file exists and is not empty
                        QEMU_PID_TO_KILL=$(cat ${QEMU_PID_FILE})
                        if [ -n "${QEMU_PID_TO_KILL}" ]; then
                            echo "Attempting to kill QEMU process with PID ${QEMU_PID_TO_KILL} using sudo..."
                            sudo kill -9 ${QEMU_PID_TO_KILL} || \
                            (echo "sudo kill failed, trying without sudo..." && kill -9 ${QEMU_PID_TO_KILL}) || \
                            echo "Failed to kill QEMU PID ${QEMU_PID_TO_KILL}."
                        else
                            echo "No QEMU PID found in ${QEMU_PID_FILE}. Searching by process name..."
                            sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill: QEMU process not found or already stopped."
                        fi
                    else
                        echo "QEMU PID file (${QEMU_PID_FILE}) not found or empty. Searching by process name..."
                        # Fallback to pgrep if PID file was empty or not created properly [cite: 207, 208]
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill: QEMU process not found or already stopped."
                    fi
                    echo "Cleanup attempt finished."
                '''
            }
        }
    }
}
