// Jenkinsfile
pipeline {
    agent any // Runs on any available agent/executor. [cite: 170]
    // For more complex needs, you might specify a Docker agent. [cite: 171]
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid' // File to store QEMU PID
    }

    stages {
        stage('Checkout SCM') {
            steps {
                git credentialsId: 'github-credentials', url: 'https://github.com/Andreas0x07/software-testing' // Use your actual repo URL [cite: 173]
                sh 'ls -la' // Verify checkout
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    echo "Setting up environment..."
                    sudo apt-get update && sudo apt-get install -y \
                        qemu-system-arm \
                        python3-venv \
                        python3-pip \
                        net-tools \
                        ipmitool \
                        unzip \
                        wget \
                        chromium-browser \
                        chromium-driver # Installs chromium and its driver
                    
                    echo "Creating Python virtual environment..."
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    
                    echo "Installing Python packages..."
                    pip install --upgrade pip
                    pip install pytest requests selenium selenium-wire locust psutil HtmlTestRunner # Added HtmlTestRunner

                    # Verify chromedriver (its path should be in PATH now)
                    which chromedriver
                    chromedriver --version
                    
                    echo "Environment setup complete."
                ''' // [cite: 174, 175]
            }
        }

        stage('Prepare OpenBMC Image') {
            steps {
                sh '''
                    echo "Downloading OpenBMC Romulus image..."
                    wget "${env.OPENBMC_IMAGE_URL}" -O romulus.zip
                    
                    echo "Unzipping Romulus image..."
                    unzip -o romulus.zip -d . # Unzip to current directory, creating 'romulus' folder
                    
                    echo "Contents of romulus directory:"
                    ls -l romulus/
                    
                    # Check if MTD file exists
                    if [ ! -f romulus/*.static.mtd ]; then
                        echo "ERROR: No .static.mtd file found in romulus directory after unzip."
                        # Attempt to find it elsewhere if the structure is different
                        find . -name '*.static.mtd' -print
                        exit 1
                    fi
                    echo "OpenBMC image prepared."
                '''
                // Set the environment variable for the OpenBMC image URL from Jenkins UI or define here
                // This uses the URL from Lab 1 [cite: 4]
                script {
                    env.OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
                }
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    sh '''
                        set +e # Don't exit immediately on error for this block
                        
                        # Check if QEMU is already running (e.g., from a previous failed build)
                        if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                            echo "QEMU already running. Attempting to kill..."
                            sudo pkill -f "qemu-system-arm -M romulus-bmc"
                            sleep 5 # Give it a moment to die
                            if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                                echo "Failed to kill existing QEMU. Exiting."
                                exit 1
                            fi
                        fi

                        echo "Finding OpenBMC MTD image file..."
                        # Find the MTD file within the 'romulus' directory
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
                        
                        # Store the PID of the nohup background process itself
                        echo $! > ${QEMU_PID_FILE}
                        # We need to find the actual QEMU process PID, as $! might be the nohup PID.
                        # Give it a second to launch, then find it.
                        sleep 5 
                        QEMU_ACTUAL_PID=$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILE}")
                        
                        if [ -z "${QEMU_ACTUAL_PID}" ]; then
                            echo "Failed to get QEMU PID. Log content:"
                            cat qemu_openbmc.log
                            exit 1
                        fi
                        echo "QEMU started with actual PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                        echo ${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE}

                        echo "Waiting for OpenBMC to boot (60 seconds)..."
                        sleep 60 
                        
                        echo "Verifying OpenBMC IPMI responsiveness..."
                        ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc chassis power status
                        if [ $? -ne 0 ]; then
                            echo "OpenBMC did not start correctly or is not responding via IPMI."
                            echo "QEMU Log (qemu_openbmc.log):"
                            cat qemu_openbmc.log
                            # Try to kill the QEMU process if it's the one we started
                            if [ -f ${QEMU_PID_FILE} ]; then
                                sudo kill -9 $(cat ${QEMU_PID_FILE}) || echo "Failed to kill QEMU PID $(cat ${QEMU_PID_FILE}), or it wasn't running."
                            fi
                            exit 1
                        fi
                        echo "OpenBMC seems to be running."
                        set -e
                    ''' // [cite: 179, 180, 181, 182, 183, 184, 185, 186, 187, 188]
                }
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    # Assuming your pytest tests from Lab 5 are in a 'tests/api' directory [cite: 145]
                    # and your test file is test_redfish.py [cite: 147]
                    # Ensure your tests are in the 'tests/api/' subdirectory of your repo
                    mkdir -p tests/api 
                    cp test_redfish.py tests/api/ 
                    pytest tests/api/test_redfish.py --junitxml=pytest_api_report.xml || echo "PyTest API tests failed or found issues."
                ''' // [cite: 190, 191]
            }
            post {
                always {
                    archiveArtifacts artifacts: 'pytest_api_report.xml, qemu_openbmc.log', fingerprint: true
                    junit 'pytest_api_report.xml' // [cite: 192]
                }
            }
        }

        stage('Run WebUI Autotests (Selenium)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    # Assuming your Selenium tests from Lab 4 are in 'tests/webui' [cite: 108]
                    # and your test file is openbmc_auth_tests.py [cite: 129]
                    # Ensure your tests are in the 'tests/webui/' subdirectory of your repo
                    mkdir -p tests/webui
                    cp openbmc_auth_tests.py tests/webui/
                    echo "Running WebUI tests..."
                    python tests/webui/openbmc_auth_tests.py || echo "Selenium WebUI tests failed or found issues."
                ''' // [cite: 193, 196]
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_report.html, qemu_openbmc.log', fingerprint: true // [cite: 199]
                    // publishHTML([allowMissing: true, alwaysLinkToLastBuild: false, keepAll: true, reportDir: '.', reportFiles: 'test_report.html', reportName: 'Selenium WebUI Report', reportTitles: ''])
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    # Assuming your Locust file from Lab 6 is locustfile.py in 'tests/load' [cite: 165]
                    # Ensure your tests are in the 'tests/load/' subdirectory of your repo
                    mkdir -p tests/load
                    cp locustfile.py tests/load/
                    echo "Starting Locust load test..."
                    # Run Locust in headless mode for a short duration for CI
                    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html || echo "Locust load test execution had issues or completed with non-zero exit."
                    # The command above runs for 30 seconds with 10 users, spawn rate 2. Adjust as needed. [cite: 202, 203]
                ''' // [cite: 201]
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
                    if [ -f ${QEMU_PID_FILE} ]; then
                        QEMU_PID_TO_KILL=$(cat ${QEMU_PID_FILE})
                        if [ -n "${QEMU_PID_TO_KILL}" ]; then
                            echo "Attempting to kill QEMU process with PID ${QEMU_PID_TO_KILL}..."
                            sudo kill -9 ${QEMU_PID_TO_KILL} || echo "Failed to kill QEMU PID ${QEMU_PID_TO_KILL}, or it wasn't running."
                        else
                            echo "No QEMU PID found in ${QEMU_PID_FILE}. Searching by process name..."
                            # Fallback to pgrep if PID file was empty or not created properly
                            sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                        fi
                    else
                        echo "QEMU PID file (${QEMU_PID_FILE}) not found. Searching by process name..."
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                    fi
                    echo "Cleanup attempt finished."
                ''' // [cite: 206, 207, 208, 209]
            }
        }
    }
}
