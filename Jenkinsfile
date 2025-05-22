// Jenkinsfile
pipeline {
    agent any // Will run on the agent defined in Jenkins UI or the default built-in node if not specified otherwise
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid'
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
        ROMULUS_DIR = 'romulus_image_files'
        OPENBMC_IMAGE_FILENAME = 'openbmc_image.static.mtd' // Consolidated image filename

        // Profiling related files
        PERF_STAT_OUTPUT = 'perf_stat_output.log'
        VMSTAT_OUTPUT = 'vmstat_output.log'
        NMON_REPORTS_DIR = 'nmon_reports' // Directory for nmon files
        QEMU_MEM_BEFORE_LOAD = 'qemu_mem_before_load.txt'
        QEMU_MEM_DURING_LOAD = 'qemu_mem_during_load.txt' // Renamed from Post-Load for clarity of collection point
        HOST_CPU_MEM_BEFORE_QEMU = 'host_cpu_mem_before_qemu.txt'
        HOST_CPU_MEM_DURING_LOAD_START = 'host_cpu_mem_at_load_start.txt' // Renamed for clarity
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
                    echo "Perf: $(which perf || echo 'perf not found')"
                    echo "Vmstat: $(which vmstat || echo 'vmstat not found')"
                    echo "Nmon: $(which nmon || echo 'nmon not found')"
                    
                    echo "Checking sudo access for jenkins user:"
                    if sudo -n true; then
                        echo "Jenkins user has passwordless sudo access."
                    else
                        echo "Jenkins user does NOT have passwordless sudo access (or sudo not found). This might cause issues later."
                        // exit 1 # Optional: fail if no sudo
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

        stage('Collect Pre-QEMU Host Metrics') {
            steps {
                sh '''
                    echo "Collecting host CPU and Memory before starting QEMU..."
                    echo "=== Top Output (CPU/Mem) ===" > ${HOST_CPU_MEM_BEFORE_QEMU}
                    top -bn1 | head -n 5 >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    echo "\n=== Free Output (Memory) ===" >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    free -m >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    echo "\n=== VMSTAT Output (System Stats) ===" >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    vmstat -S M 1 2 >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    echo "\n=== DF Output (Disk Space) ===" >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    df -h >> ${HOST_CPU_MEM_BEFORE_QEMU}
                    echo "Host metrics before QEMU collected into ${HOST_CPU_MEM_BEFORE_QEMU}"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${HOST_CPU_MEM_BEFORE_QEMU}", fingerprint: true
                }
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
                    set +e # Allow script to manage errors for QEMU start

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

                    echo "Starting QEMU with OpenBMC wrapped in perf stat..."
                    nohup perf stat -o ${PERF_STAT_OUTPUT} -e cycles,instructions,cache-misses,cpu-migrations,context-switches,page-faults \\
                        qemu-system-arm \\
                        -m 256 \\
                        -M romulus-bmc \\
                        -nographic \\
                        -drive file=${OPENBMC_IMAGE_FILENAME},format=raw,if=mtd \\
                        -net nic \\
                        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                        > ${QEMU_LOG} 2>&1 &
                    
                    PERF_QEMU_NOHUP_PID=$!
                    echo "Nohup PERF_STAT+QEMU process potentially started with PID ${PERF_QEMU_NOHUP_PID}."
                    
                    sleep 15 # Increased sleep to allow QEMU to fully start under perf

                    QEMU_ACTUAL_PID=""
                    # Try to find the QEMU process itself, which is a child of perf.
                    # The command for pgrep needs to be specific to avoid matching other qemu instances.
                    # The OPENBMC_IMAGE_FILENAME is crucial here.
                    QEMU_PGREP_PID=$(pgrep -f "qemu-system-arm -M romulus-bmc -nographic -drive file=${OPENBMC_IMAGE_FILENAME}")

                    if [ -n "${QEMU_PGREP_PID}" ]; then
                        # In case pgrep returns multiple PIDs (e.g., threads), take the first one.
                        # This assumes the main QEMU process matches this pattern.
                        QEMU_ACTUAL_PID=$(echo ${QEMU_PGREP_PID} | awk '{print $1}')
                        echo "QEMU process found via pgrep with PID ${QEMU_ACTUAL_PID}."
                        # Verify it's a child of the nohup'd perf process if possible, for added certainty (optional)
                        # PERF_PID_FROM_QEMU_PARENT=$(ps -o ppid= -p ${QEMU_ACTUAL_PID} | xargs)
                        # echo "QEMU's parent PID is ${PERF_PID_FROM_QEMU_PARENT}. Perf's PID was ${PERF_QEMU_NOHUP_PID}."
                    else
                        echo "Could not find QEMU process via pgrep after starting with perf."
                        echo "Perf/QEMU Log (${QEMU_LOG}) content:"
                        cat ${QEMU_LOG}
                        echo "Listing current qemu processes (if any) via ps:"
                        ps aux | grep qemu-system-arm | grep -v grep
                        exit 1
                    fi
                    
                    echo "QEMU (child of perf) confirmed running with PID ${QEMU_ACTUAL_PID}. Storing to ${QEMU_PID_FILE}."
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
                    set -e # Resume failing on errors
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
                            if [ "${HTTP_CODE}" != "200" ] && [ "${HTTP_CODE}" != "401" ]; then # 401 is OK for /redfish/v1/ if auth is required
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
                        # ... (rest of debugging commands from original Jenkinsfile)
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
        
        stage('Collect Pre-Load QEMU/Host Metrics') {
            steps {
                sh '''
                    echo "Collecting QEMU memory and host CPU/memory before load testing..."
                    QEMU_PID=$(cat ${QEMU_PID_FILE})
                    if [ -n "${QEMU_PID}" ] && ps -p ${QEMU_PID} > /dev/null; then
                        echo "QEMU PID: ${QEMU_PID}"
                        echo "=== QEMU Process Info (ps) Before Load ===" > ${QEMU_MEM_BEFORE_LOAD}
                        ps -p ${QEMU_PID} -o pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,cmd >> ${QEMU_MEM_BEFORE_LOAD}
                        QEMU_RSS_KB=$(ps -p ${QEMU_PID} -o rss= | awk '{print $1}')
                        if [ -n "${QEMU_RSS_KB}" ]; then
                            echo "QEMU Current Memory (RSS): ${QEMU_RSS_KB} KB ($((QEMU_RSS_KB / 1024)) MB)" >> ${QEMU_MEM_BEFORE_LOAD}
                        else
                            echo "Could not get QEMU RSS" >> ${QEMU_MEM_BEFORE_LOAD}
                        fi
                    else
                        echo "QEMU_PID ${QEMU_PID} not found or not running!" > ${QEMU_MEM_BEFORE_LOAD}
                    fi
                    echo "QEMU memory metrics collected into ${QEMU_MEM_BEFORE_LOAD}"

                    echo "=== Host CPU/Mem at Load Start (top) ===" > ${HOST_CPU_MEM_DURING_LOAD_START}
                    top -bn1 | head -n 5 >> ${HOST_CPU_MEM_DURING_LOAD_START}
                    echo "\n=== Host Free at Load Start (free) ===" >> ${HOST_CPU_MEM_DURING_LOAD_START}
                    free -m >> ${HOST_CPU_MEM_DURING_LOAD_START}
                    echo "Host CPU/Mem collected into ${HOST_CPU_MEM_DURING_LOAD_START}"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${QEMU_MEM_BEFORE_LOAD}, ${HOST_CPU_MEM_DURING_LOAD_START}", fingerprint: true, allowEmptyArchive: true
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    echo "Waiting for 30 seconds before starting Locust to allow OpenBMC to settle..."
                    sleep 30
                    
                    . ${PYTHON_VENV}/bin/activate
                    
                    echo "Starting profiling tools (vmstat, nmon)..."
                    # vmstat: interval 1s, count 70 (for 60s test + buffer). Output in MB.
                    vmstat -S M 1 70 > ${VMSTAT_OUTPUT} &
                    VMSTAT_PID=$!
                    echo "vmstat started with PID ${VMSTAT_PID}"

                    rm -rf ${NMON_REPORTS_DIR}/*.nmon # Clean up old nmon files
                    mkdir -p ${NMON_REPORTS_DIR}
                    # nmon: snapshot every 5s, 15 snapshots (75s duration), -f for spreadsheet format, -T for top procs
                    # Naming: -N (net), -D (disk), -K (kernel), -U (util)
                    nmon -f -s 5 -c 15 -T -N -D -K -U -m ./${NMON_REPORTS_DIR} &
                    NMON_PID=$!
                    echo "nmon started with PID ${NMON_PID}"
                    
                    echo "Starting Locust load test..."
                    locust -f locustfile.py --headless -u 2 -r 1 1 -t 60s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html
                    
                    echo "Load test finished. Waiting for profiling tools to complete..."
                    # Wait for vmstat to finish (it runs for a fixed count)
                    if ps -p ${VMSTAT_PID} > /dev/null; then wait ${VMSTAT_PID} || echo "vmstat already finished"; fi
                    echo "vmstat finished."
                    
                    # nmon runs in background and stops after -c count.
                    # Give it a few more seconds to ensure it finishes writing its file.
                    sleep 10 
                    if ps -p ${NMON_PID} > /dev/null; then 
                        echo "Nmon process ${NMON_PID} still running, sending SIGUSR2 to stop."
                        sudo kill -SIGUSR2 ${NMON_PID} || echo "Failed to send SIGUSR2 to nmon, or it already stopped."
                        sleep 2 # Give nmon time to react to SIGUSR2
                        if ps -p ${NMON_PID} > /dev/null; then
                           echo "Nmon ${NMON_PID} did not stop with SIGUSR2, using SIGTERM."
                           sudo kill -SIGTERM ${NMON_PID} || echo "Nmon already stopped."
                        fi
                    fi
                    echo "nmon should be finished."
                    
                    # List nmon files generated
                    echo "NMON files generated in ./${NMON_REPORTS_DIR}:"
                    ls -l ./${NMON_REPORTS_DIR}
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "locust_report_stats.csv, locust_report_stats_history.csv, locust_report.html, ${QEMU_LOG}, ${VMSTAT_OUTPUT}, ${NMON_REPORTS_DIR}/*.nmon", fingerprint: true, allowEmptyArchive: true
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

        stage('Collect Post-Load QEMU Metrics') {
            steps {
                sh '''
                    echo "Collecting QEMU memory after load testing..."
                    QEMU_PID=$(cat ${QEMU_PID_FILE})
                    if [ -n "${QEMU_PID}" ] && ps -p ${QEMU_PID} > /dev/null; then
                        echo "QEMU PID: ${QEMU_PID}"
                        echo "=== QEMU Process Info (ps) After Load ===" > ${QEMU_MEM_DURING_LOAD}
                        ps -p ${QEMU_PID} -o pid,ppid,user,%cpu,%mem,vsz,rss,stat,start,time,cmd >> ${QEMU_MEM_DURING_LOAD}
                        QEMU_RSS_KB=$(ps -p ${QEMU_PID} -o rss= | awk '{print $1}')
                        if [ -n "${QEMU_RSS_KB}" ]; then
                            echo "QEMU Current Memory (RSS): ${QEMU_RSS_KB} KB ($((QEMU_RSS_KB / 1024)) MB)" >> ${QEMU_MEM_DURING_LOAD}
                        else
                            echo "Could not get QEMU RSS" >> ${QEMU_MEM_DURING_LOAD}
                        fi
                    else
                        echo "QEMU_PID ${QEMU_PID} not found or not running!" > ${QEMU_MEM_DURING_LOAD}
                    fi
                    echo "QEMU memory metrics collected into ${QEMU_MEM_DURING_LOAD}"
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: "${QEMU_MEM_DURING_LOAD}", fingerprint: true, allowEmptyArchive: true
                }
            }
        }
    } // End of stages

    post {
        always {
            script {
                // Archive perf_stat_output.log here, as it's generated after QEMU (and perf) stop.
                // This requires QEMU to be stopped first.
                sh '''
                    echo "Pipeline finished. Cleaning up QEMU..."
                    QEMU_PID_TO_KILL=""
                    PERF_PID_TO_KILL=""

                    if [ -f ${QEMU_PID_FILE} ]; then
                        QEMU_PID_FROM_FILE=$(cat ${QEMU_PID_FILE})
                        if [ -n "${QEMU_PID_FROM_FILE}" ] && ps -p ${QEMU_PID_FROM_FILE} > /dev/null; then
                            QEMU_PID_TO_KILL=${QEMU_PID_FROM_FILE}
                            # Try to find the parent perf process to kill it first, so it generates its report
                            PERF_PID_TO_KILL=$(ps -o ppid= -p ${QEMU_PID_TO_KILL} | xargs)
                        fi
                    fi
                    
                    # If we have a perf PID, try to kill it gracefully first then forcefully
                    if [ -n "${PERF_PID_TO_KILL}" ] && ps -p ${PERF_PID_TO_KILL} > /dev/null && \
                       [ "$(ps -o comm= -p ${PERF_PID_TO_KILL})" = "perf" ]; then
                        echo "Attempting to kill perf process with PID ${PERF_PID_TO_KILL} (parent of QEMU)..."
                        sudo kill -SIGINT ${PERF_PID_TO_KILL} # Perf should handle SIGINT and write its file
                        sleep 5 # Give perf time to write the file
                        if ps -p ${PERF_PID_TO_KILL} > /dev/null; then
                            echo "Perf process ${PERF_PID_TO_KILL} still running, using SIGKILL."
                            sudo kill -9 ${PERF_PID_TO_KILL}
                        fi
                        echo "Perf process ${PERF_PID_TO_KILL} stopped."
                    elif [ -n "${QEMU_PID_TO_KILL}" ]; then
                        # If no clear perf PID, or if it was the same as QEMU (should not happen with current setup)
                        # just kill QEMU. Perf might not generate a report cleanly in this edge case.
                        echo "Attempting to kill QEMU process directly with PID ${QEMU_PID_TO_KILL}..."
                        sudo kill -9 ${QEMU_PID_TO_KILL}
                        echo "Killed QEMU PID ${QEMU_PID_TO_KILL}."
                    else
                        echo "No specific QEMU or Perf PID found from ${QEMU_PID_FILE}. Searching by process name..."
                        sudo pkill -SIGINT -f "perf stat -o ${PERF_STAT_OUTPUT}.*qemu-system-arm" # Try to stop perf gracefully
                        sleep 2
                        sudo pkill -9 -f "qemu-system-arm -M romulus-bmc" || echo "pkill attempt: QEMU process not found or already stopped."
                        sudo pkill -9 -f "perf stat -o ${PERF_STAT_OUTPUT}" || echo "pkill attempt: Perf process not found or already stopped."
                    fi
                    
                    rm -f ${QEMU_PID_FILE}
                    echo "Cleanup attempt finished."
                    
                    echo "Final check for running QEMU/Perf processes:"
                    ps aux | grep -E "qemu-system-arm|perf stat" | grep -v grep || echo "No relevant qemu-system-arm or perf stat processes found."
                '''
                archiveArtifacts artifacts: "${PERF_STAT_OUTPUT}, ${QEMU_LOG}", allowEmptyArchive: true, fingerprint: true
            }
        }
    }
}
