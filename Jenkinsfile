pipeline {
    agent any // Runs on any available agent/executor. For more complex needs, you might specify a Docker agent.

    environment {
        QEMU_PID = ''
        OPENBMC_IMAGE_PATH = 'openbmc/build/tmp/deploy/images/romulus/obmc-phosphor-image-romulus-xxxxxxxxxxxxxx.static.mtd' // Adjust with your actual image path from Lab 1 [cite: 4]
        ROMULUS_FILES_PATH = 'romulus' // Path to the directory containing the unzipped romulus files [cite: 4]
        PYTHON_VENV = 'venv_jenkins'
    }

    stages {
        stage('Checkout SCM') {
            steps {
                git credentialsId: 'github-credentials', url: 'your-github-repo-url' // Configure credentials in Jenkins
                sh 'ls -la' // Verify checkout
            }
        }

        stage('Setup Environment') {
            steps {
                sh '''
                    sudo apt-get update && sudo apt-get install -y qemu-system-arm python3-venv python3-pip net-tools ipmitool
                    python3 -m venv ${PYTHON_VENV}
                    . ${PYTHON_VENV}/bin/activate
                    pip install pytest requests selenium selenium-wire locust psutil
                    # Download WebDriver if not already in repo (ensure it's executable)
                    # Example for ChromeDriver:
                    # wget https://storage.googleapis.com/chrome-for-testing-public/.../linux64/chromedriver-linux64.zip -O chromedriver.zip
                    # unzip chromedriver.zip
                    # sudo mv chromedriver-linux64/chromedriver /usr/local/bin/
                    # Ensure your Selenium scripts point to the correct WebDriver path or it's in PATH
                '''
            }
        }

        stage('Start QEMU with OpenBMC') {
            steps {
                script {
                    // Ensure the OpenBMC image from Lab 1 is available at the correct path [cite: 4]
                    // Make sure the 'romulus' directory from unzipping romulus.zip is present [cite: 4]
                    sh '''
                        set +e # Don't exit immediately on error for this block
                        # Check if QEMU is already running from a previous build on the same executor
                        pgrep -f "qemu-system-arm -M romulus-bmc" && echo "QEMU already running?" && exit 1

                        echo "Starting QEMU with OpenBMC..."
                        nohup qemu-system-arm \\
                            -m 256 \\
                            -M romulus-bmc \\
                            -nographic \\
                            -drive file=${env.OPENBMC_IMAGE_PATH},format=raw,if=mtd \\
                            -net nic \\
                            -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \\
                            > qemu_openbmc.log 2>&1 &
                        QEMU_PID=$!
                        echo "QEMU started with PID ${QEMU_PID}"
                        sleep 60 # Give OpenBMC time to boot
                        # Verify OpenBMC is responding (e.g. ping or curl if possible, or just assume it's up)
                        # For example, trying an IPMI command like in Lab 1 [cite: 5]
                        ipmitool -I lanplus -H 127.0.0.1 -p 2623 -U root -P 0penBmc chassis power status
                        if [ $? -ne 0 ]; then
                            echo "OpenBMC did not start correctly."
                            # Try to kill the QEMU process if it's the one we started
                            kill ${QEMU_PID} || echo "Failed to kill QEMU PID ${QEMU_PID}, or it wasn't running."
                            exit 1
                        fi
                        set -e
                    '''
                }
            }
        }

        stage('Run API Autotests (PyTest)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    # Assuming your pytest tests from Lab 5 are in a 'tests/api' directory [cite: 145]
                    # and your test file is test_redfish.py [cite: 147]
                    pytest tests/api/test_redfish.py --junitxml=pytest_api_report.xml || echo "PyTest API tests failed"
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
                    # Assuming your Selenium tests from Lab 4 are in 'tests/webui' [cite: 108]
                    # and your test file is openbmc_auth_tests.py [cite: 129, 130, 131, 132, 133, 134]
                    # Ensure chromedriver is in PATH or its path is configured in your Selenium script
                    # For headless operation, your Selenium script needs to be configured for it.
                    # Your script uses chrome_options.add_argument('--headless') but it's commented out[cite: 129].
                    # Uncomment it or ensure it's set for CI.
                    python tests/webui/openbmc_auth_tests.py || echo "Selenium WebUI tests failed"
                    # If your tests generate a report (e.g., XML), refer to it here.
                    # For now, we'll assume pass/fail is based on exit code.
                '''
            }
            post {
                always {
                    // Archive any logs or reports generated by Selenium tests.
                    // For example, if you modify your script to output a log:
                    // archiveArtifacts artifacts: 'selenium_report.log, qemu_openbmc.log', fingerprint: true
                    // If using unittest and want JUnit compatible reports, you might need a test runner like xmlrunner
                }
            }
        }

        stage('Run Load Testing (Locust)') {
            steps {
                sh '''
                    . ${PYTHON_VENV}/bin/activate
                    # Assuming your Locust file from Lab 6 is locustfile.py in 'tests/load' [cite: 165, 167, 168, 169]
                    echo "Starting Locust load test..."
                    # Run Locust in headless mode for a short duration for CI
                    locust -f tests/load/locustfile.py --headless -u 10 -r 2 -t 30s --host=https://localhost:2443 --csv=locust_report --html=locust_report.html || echo "Locust load test execution had issues"
                    # The command above runs for 30 seconds with 10 users, spawn rate 2. Adjust as needed.
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'locust_report_stats.csv, locust_report_stats_history.csv, locust_report.html, qemu_openbmc.log', fingerprint: true
                }
            }
        }
    }

    post {
        always {
            script {
                sh '''
                    echo "Pipeline finished. Cleaning up QEMU..."
                    # Attempt to find and kill the QEMU process started by this pipeline
                    # This is a simple approach; more robust solutions might involve tracking the exact PID
                    pgrep -f "qemu-system-arm -M romulus-bmc" | xargs --no-run-if-empty sudo kill -9
                    echo "Cleanup attempt finished."
                '''
            }
        }
    }
}
