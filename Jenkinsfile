// Jenkinsfile
pipeline {
    agent any // Will run on the agent defined in Jenkins UI or the default built-in node if not specified otherwise
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid'
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
        ROMULUS_DIR = 'romulus_image_files'
        OPENBMC_IMAGE_FILENAME = 'openbmc_image.static.mtd' // Consolidated image filename
        QEMU_LOG = 'qemu_openbmc.log'
    }

    stages {
        stage('Checkout SCM') {
            steps {
                // Implicit checkout by Jenkins SCM configuration
                sh 'echo "Workspace content after implicit checkout:"'
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
                    echo "Chromium Driver: $(which chromedriver || which chromium-driver || echo 'chromedriver not found')"
                    echo "Chromium: $(which chromium || echo 'chromium not found')"
                    
                    echo "Checking sudo access for jenkins user:"
                    if sudo -n true; then
                        echo "Jenkins user has passwordless sudo access."
                    else
                        echo "Jenkins user does NOT have passwordless sudo access (or sudo not found). This might cause issues later."
                        // exit 1 // Optional: fail if no sudo
                    fi

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
                         
                    echo "Cleaning up old OpenBMC image directory..."
                    rm -rf ./${ROMULUS_DIR}
                    mkdir ./${ROMULUS_DIR}
                      
                    echo "Unzipping Romulus image into ./${ROMULUS_DIR}..."
                    unzip -o romulus.zip -d ./${ROMULUS_DIR}
                    
                    echo "Contents of ./${ROMULUS_DIR} directory (after unzip, it should contain a 'romulus' subfolder):"
                    ls -l ./${ROMULUS_DIR}
                    echo "Contents of ./${ROMULUS_DIR}/romulus/ directory:"
                    ls -l ./${ROMULUS_DIR}/romulus/ 
                    
                    OPENBMC_MTD_CANDIDATE=$(find ./${ROMULUS_DIR}/romulus -name '*.static.mtd' -print -quit)
                    
                    if [ -z "${OPENBMC_MTD_CANDIDATE}" ] || [ ! -f "${OPENBMC_MTD_CANDIDATE}" ]; then
                        echo "ERROR: No .static.mtd file found in ./${ROMULUS_DIR}/romulus/ after unzip."
                        echo "Listing current directory structure:"
                        ls -R .
                        exit 1
                    fi
                    cp "${OPENBMC_MTD_CANDIDATE}" ./${OPENBMC_IMAGE_FILENAME}
                    echo "OpenBMC image prepared: ./${OPENBMC_IMAGE_FILENAME} (copied from ${OPENBMC_MTD_CANDIDATE})"
                '''
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                sh '''
                    set +e // Allow script to manage errors for QEMU start

                    if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                        echo "QEMU (romulus-bmc) already running. Attempting to kill..."
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" 
                        sleep 5 
                        if pgrep -f "qemu-system-arm -M romulus-bmc"; then
                            echo "Failed to kill existing QEMU. Exiting."
                            exit 1
                        fi
                    fi

                    if [ ! -f "${OPENBMC_IMAGE_FILENAME}" ]; then
                        echo "ERROR: OpenBMC MTD image file ${OPENBMC_IMAGE_FILENAME} not found."
                        exit 1
                    fi
                    echo "Using MTD image: ${OPENBMC_IMAGE_FILENAME}"

                    echo "Starting QEMU with OpenBMC..."
                    nohup qemu-system-arm \\
                        -m 256 \\
                        -M romulus-bmc \\
                        -nographic \\
                        -drive file=${OPENBMC_IMAGE_FILENAME},format=raw,if=mtd \\
                        -net nic \\
                        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                        > ${QEMU_LOG} 2>&1 &
                    
                    QEMU_NOHUP_PID=$!
                    echo "Nohup QEMU process potentially started with PID ${QEMU_NOHUP_PID}."
                    
                    sleep 15 // Increased sleep to allow QEMU to fully start

                    QEMU_ACTUAL_PID=""
                    QEMU_PGREP_PID=$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILENAME}")

                    if [ -n "${QEMU_PGREP_PID}" ]; then
                        QEMU_ACTUAL_PID=$(echo ${QEMU_PGREP_PID} | awk '{print $1}')
                        echo "QEMU process found via pgrep with PID ${QEMU_ACTUAL_PID}."
                    else
                        echo "Could not find QEMU process via pgrep after starting."
                        echo "QEMU Log (${QEMU_LOG}) content:"
                        cat ${QEMU_LOG}
                        echo "Listing current qemu processes (if any) via ps:"
                        ps aux | grep qemu-system-arm | grep -v grep
                        exit 1
                    fi
                    
                    echo "QEMU confirmed running with PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
                    echo ${QEMU_ACTUAL_PID} > ${QEMU_PID_FILE}

                    echo "Waiting for OpenBMC to boot (180 seconds initial wait)..." 
                    sleep 180
                    
                    echo "Verifying OpenBMC IPMI responsiveness with retries..."
                    RETRY_COUNT=0
                    MAX_RETRIES=6 
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
                        echo "QEMU Log (${QEMU_LOG}):"
                        cat ${QEMU_LOG} || echo "Failed to cat ${QEMU_LOG}"
                        if [ -f ${QEMU_PID_FILE} ]; then
                            echo "Attempting to kill QEMU PID $(cat ${QEMU_PID_FILE})..."
                            sudo kill -9 $(cat ${QEMU_PID_FILE}) || echo "Failed to kill QEMU PID $(cat ${QEMU_PID_FILE}), or it wasn't running."
                        else
                             sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pgrep kill attempt: QEMU process not found or already stopped."
                        fi
                        exit 1
                    fi
                    echo "OpenBMC seems to be running (IPMI responsive)."
                    set -e // Resume failing on errors
                '''
            }
        }

        stage('Verify Web Service Availability') {
            steps {
                sh '''
                    echo "Waiting an additional 90 seconds for web services (Redfish) to fully initialize..." 
                    sleep 90

                    echo "Attempting to connect to https://localhost:2443/redfish/v1/ ..."
                    RETRY_COUNT=0
                    MAX_RETRIES=6 
                    WEB_SVC_SUCCESS=0
                    while [ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]; do
                        echo "Web service check attempt $((RETRY_COUNT + 1)) of ${MAX_RETRIES}..."
                        HTTP_CODE=$(curl --head --silent --insecure --max-time 15 --connect-timeout 10 --output /dev/null --write-out "%{http_code}" https://localhost:2443/redfish/v1/)
                        
                        echo "Received HTTP_CODE: ${HTTP_CODE}"
                        if [ "${HTTP_CODE}" -ge 200 ] && [ "${HTTP_CODE}" -lt 500 ]; then
                            WEB_SVC_SUCCESS=1
                            echo "Web service responded with HTTP_CODE: ${HTTP_CODE}."
                            if [ "${HTTP_CODE}" != "200" ] && [ "${HTTP_CODE}" != "401" ]; then // 401 is OK for /redfish/v1/ if auth is required
                                echo "WARNING: Expected HTTP 200 or 401 for GET /redfish/v1/ but received ${HTTP_CODE}."
                                echo "This might indicate an issue, but the service is up. Proceeding with tests..."
                            else
                                echo "Web service responded with ${HTTP_CODE}. Proceeding with tests."
                            fi
                            break
                        elif [ "${HTTP_CODE}" = "000" ]; then
                            echo "Web service check failed (curl code 000 - likely connection issue, DNS problem, or timeout before response headers)."
                        else
                            echo "Web service check failed with unexpected HTTP_CODE: ${HTTP_CODE} (e.g. 5xx Server Error)."
                        fi
                        
                        RETRY_COUNT=$((RETRY_COUNT + 1))
                        if [ ${RETRY_COUNT} -lt ${MAX_RETRIES} ]; then
                            echo "Retrying in 10 seconds..."
                            sleep 10
                        else
                            echo "Web service check failed on final attempt (Last HTTP_CODE: ${HTTP_CODE})."
                        fi
                    done

                    if [ ${WEB_SVC_SUCCESS} -ne 1 ]; then
                        echo "OpenBMC Web Service on port 2443 is NOT considered available after multiple attempts."
                        echo "QEMU Log (${QEMU_LOG}) for review:"
                        cat ${QEMU_LOG} || echo "Failed to cat ${QEMU_LOG}"
                        exit 1
                    fi
                '''
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    pytest test_redfish.py --junitxml=pytest_api_report.xml
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "pytest_api_report.xml, ${QEMU_LOG}", fingerprint: true, allowEmptyArchive: true
                    junit 'pytest_api_report.xml'
                }
            }
        }

        stage('Run WebUI Autotests (Selenium)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    echo "Running WebUI tests..."
                    python openbmc_auth_tests.py
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_report.html, ${QEMU_LOG}', fingerprint: true, allowEmptyArchive: true
                    publishHTML([
                        allowMissing: true, 
                        alwaysLinkToLastBuild: false, 
                        keepAll: true, 
                        reportDir: '.', 
                        reportFiles: 'test_report.html', 
                        reportName: 'Selenium WebUI Report', 
                        reportTitles: ''
                    ])
                }
            }
        }
        
        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    echo "Waiting for 30 seconds before starting Locust to allow OpenBMC to settle..."
                    sleep 30
                                     
                    . ${PYTHON_VENV}/bin/activate
                                        
                    echo "Starting Locust load test..."
                    locust -f locustfile.py --headless -u 10 -r 2 -t 60s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html
                                       
                    echo "Load test finished."
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "locust_report_stats.csv, locust_report_stats_history.csv, locust_report.html, ${QEMU_LOG}", fingerprint: true, allowEmptyArchive: true
                    publishHTML([
                        allowMissing: true, 
                        alwaysLinkToLastBuild: false, 
                        keepAll: true, 
                        reportDir: '.', 
                        reportFiles: 'locust_report.html', 
                        reportName: 'Locust Load Test Report', 
                        reportTitles: ''
                    ])
                }
            }
        }
    } // End of stages

    post {
        always {
            script {
                sh '''
                    echo "Pipeline finished. Cleaning up QEMU..."
                    QEMU_PID_TO_KILL=""

                    if [ -f ${QEMU_PID_FILE} ]; then
                        QEMU_PID_FROM_FILE=$(cat ${QEMU_PID_FILE})
                        if [ -n "${QEMU_PID_FROM_FILE}" ] && ps -p ${QEMU_PID_FROM_FILE} > /dev/null; then
                            QEMU_PID_TO_KILL=${QEMU_PID_FROM_FILE}
                        fi
                    fi
                    
                    if [ -n "${QEMU_PID_TO_KILL}" ]; then
                        echo "Attempting to kill QEMU process with PID ${QEMU_PID_TO_KILL}..."
                        sudo kill -9 ${QEMU_PID_TO_KILL}
                        echo "Killed QEMU PID ${QEMU_PID_TO_KILL}."
                    else
                        echo "No specific QEMU PID found from ${QEMU_PID_FILE}. Searching by process name..."
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill attempt: QEMU process not found or already stopped."
                    fi
                    
                    rm -f ${QEMU_PID_FILE}
                    echo "Cleanup attempt finished."
                    echo "Final check for running QEMU processes:"
                    ps aux | grep "qemu-system-arm -M romulus-bmc" | grep -v grep || echo "No relevant qemu-system-arm processes found."
                '''
                archiveArtifacts artifacts: "${QEMU_LOG}", allowEmptyArchive: true, fingerprint: true
            }
        }
    }
}
