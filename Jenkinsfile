// Jenkinsfile
pipeline {
    agent any
    environment {
        PYTHON_VENV = 'venv_jenkins'
        QEMU_PID_FILE = 'qemu.pid'
        OPENBMC_IMAGE_URL = 'https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip'
        ROMULUS_DIR = 'romulus_image_files'
        LOCUST_RUN_DURATION = '60s' // Matches -t 60s in locust command
        PROFILING_DURATION = 60 // In seconds, matches LOCUST_RUN_DURATION
    }

    stages {
        stage('Checkout SCM') {
            steps {
                sh 'echo "Workspace content after implicit checkout:"'
                sh 'ls -la'
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    echo "Running in custom Docker agent. System packages should be pre-installed."
                    echo "Verifying key installations..."
                    echo "Git version: $(git --version || echo 'git not found')"`
                    echo "QEMU: $(which qemu-system-arm || echo 'qemu-system-arm not found')"`
                    echo "Python3: $(which python3 || echo 'python3 not found')"`
                    echo "pip3: $(which pip3 || echo 'pip3 not found')"`
                    echo "IPMItool: $(which ipmitool || echo 'ipmitool not found')"`
                    echo "Chromium Driver: $(which chromedriver || which chromium-driver || echo 'chromedriver not found')"`
                    echo "Chromium: $(which chromium || echo 'chromium not found')"`
                    echo "perf: $(which perf || echo 'perf not found')"`
                    echo "vmstat: $(which vmstat || echo 'vmstat not found')"`
                    echo "nmon: $(which nmon || echo 'nmon not found')"`

                    echo "Checking sudo access for jenkins user (should not ask for password):"
                    sudo -n echo "Sudo access confirmed." || echo "Sudo access FAILED!"

                    # Setup Python virtual environment
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements.txt || echo "requirements.txt not found, skipping."
                    pip install locust
                    pip install beautifulsoup4
                    pip install requests
                    pip install selenium
                    pip install webdriver_manager
                    deactivate
                '''
                // Before QEMU Launch - Host Metrics (CPU)
                sh 'echo "Collecting Host CPU (%) before test (vmstat 1 1):"'
                sh 'vmstat 1 1 > vmstat_before_test.log'
            }
        }

        stage('Download and Extract OpenBMC Image') {
            steps {
                script {
                    def romulusZip = "${ROMULUS_DIR}/romulus.zip"
                    sh "mkdir -p ${ROMULUS_DIR}"
                    sh "wget -O ${romulusZip} ${OPENBMC_IMAGE_URL}"
                    sh "unzip -o ${romulusZip} -d ${ROMULUS_DIR}"
                    sh "ls -la ${ROMULUS_DIR}"
                }
            }
        }

        stage('Launch QEMU with OpenBMC') {
            steps {
                sh '''
                    echo "Launching QEMU with OpenBMC in background..."
                    nohup qemu-system-arm \\
                        -m 256 \\
                        -M romulus-bmc \\
                        -nographic \\
                        -drive file=${ROMULUS_DIR}/obmc-phosphor-image-romulus-20250212052422.static.mtd,format=raw,if=mtd \\
                        -net nic,model=ftgmac100 \\
                        -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=tcp::5555-:5555 \\
                        -monitor telnet:127.0.0.1:5555,server,nowait \\
                        -serial mon:stdio \\
                        > qemu_openbmc.log 2>&1 &
                    echo $! > ${QEMU_PID_FILE}
                    echo "QEMU PID saved to ${QEMU_PID_FILE}"
                    sleep 10 # Give QEMU a moment to start
                '''
                sh 'echo "Waiting for OpenBMC to boot up (approx 2 minutes)..."'
                sh 'sleep 120' // Increased sleep time for boot
                sh 'echo "OpenBMC boot up wait complete."'
            }
        }

        stage('Run Unit Tests') {
            steps {
                sh '''
                    echo "Activating virtual environment for unit tests..."
                    . ${PYTHON_VENV}/bin/activate
                    echo "Running OpenBMC authentication tests..."
                    python3 openbmc_auth_tests.py
                    deactivate
                '''
            }
            post {
                always {
                    // Assuming tests generate some output that can be captured if needed
                    // For now, relying on console output for pass/fail indication
                }
            }
        }

        stage('Run WebUI Tests') {
            steps {
                sh '''
                    echo "Activating virtual environment for WebUI tests..."
                    . ${PYTHON_VENV}/bin/activate
                    echo "Running WebUI tests..."
                    # Ensure chromedriver is executable and in PATH, as handled by Dockerfile
                    python3 test_redifsh.py
                    deactivate
                '''
            }
            post {
                always {
                    // Assuming tests generate some output that can be captured if needed
                    // For now, relying on console output for pass/fail indication
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh 'echo "Waiting for 30 seconds before starting Locust to allow OpenBMC to settle..."'
                sh 'sleep 30'
                script {
                    // Get QEMU PID for perf stat
                    def qemuPid = sh(script: "cat ${QEMU_PID_FILE}", returnStdout: true).trim()
                    echo "QEMU PID for profiling: ${qemuPid}"

                    // Start profiling tools in background
                    sh "nohup vmstat 1 > vmstat_during_test.log 2>&1 & echo \$! > vmstat.pid"
                    sh "nohup nmon -F nmon_during_test.nmon -s 1 -c ${PROFILING_DURATION} > /dev/null 2>&1 & echo \$! > nmon.pid"
                    sh "nohup perf stat -p ${qemuPid} -e cycles,instructions,cache-misses sleep ${PROFILING_DURATION} > perf_during_test.log 2>&1 & echo \$! > perf.pid"

                    sh '''
                        echo "Starting Locust load test..."
                        . ${PYTHON_VENV}/bin/activate
                        locust -f locustfile.py --headless -u 2 -r 1 -t ${LOCUST_RUN_DURATION} --host=https://localhost:2443 --html locust_report.html --csv locust_report --logfile locust_console.log
                        deactivate
                    '''
                }
            }
            post {
                always {
                    script {
                        // Kill profiling processes
                        echo "Killing profiling processes..."
                        def vmstatPid = sh(script: "cat vmstat.pid || echo ''", returnStdout: true).trim()
                        if (vmstatPid) {
                            sh "sudo kill -9 ${vmstatPid} || true" // `|| true` to prevent failure if process already gone
                            sh "rm -f vmstat.pid"
                            echo "Killed vmstat PID ${vmstatPid}."
                        }

                        def nmonPid = sh(script: "cat nmon.pid || echo ''", returnStdout: true).trim()
                        if (nmonPid) {
                            sh "sudo kill -9 ${nmonPid} || true"
                            sh "rm -f nmon.pid"
                            echo "Killed nmon PID ${nmonPid}."
                        }

                        def perfPid = sh(script: "cat perf.pid || echo ''", returnStdout: true).trim()
                        if (perfPid) {
                            sh "sudo kill -9 ${perfPid} || true"
                            sh "rm -f perf.pid"
                            echo "Killed perf PID ${perfPid}."
                        }
                    }

                    echo "Archive the artifacts"
                    archiveArtifacts artifacts: 'locust_report.html, locust_report.csv, locust_report_stats.csv, locust_report_stats_history.csv, locust_console.log, vmstat_before_test.log, vmstat_during_test.log, nmon_during_test.nmon, perf_during_test.log'

                    echo "Publish HTML reports"
                    publishHTML(target: [
                        allowMissing: false,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: '.',
                        reportFiles: 'locust_report.html',
                        reportName: 'Locust Load Test Report'
                    ])
                }
            }
        }
    }

    post {
        always {
            stage('Declarative: Post Actions') {
                steps {
                    script {
                        echo "Pipeline finished. Cleaning up QEMU..."
                        if (fileExists(env.QEMU_PID_FILE)) {
                            def qemuPidToKill = readFile(env.QEMU_PID_FILE).trim()
                            if (qemuPidToKill) {
                                echo "Attempting to kill QEMU process with PID ${qemuPidToKill}..."
                                // Check if the process is still running before attempting to kill
                                sh "ps -p ${qemuPidToKill} && sudo kill -9 ${qemuPidToKill} || echo 'QEMU process not found or already terminated.'"
                                echo "Killed QEMU PID ${qemuPidToKill}."
                            }
                            sh "rm -f ${env.QEMU_PID_FILE}"
                        }
                        echo "Cleanup attempt finished."
                        echo "Final check for running QEMU..."
                        sh "ps aux | grep qemu-system-arm | grep -v grep || echo 'No QEMU processes found.'"
                    }
                }
            }
        }
    }
}
