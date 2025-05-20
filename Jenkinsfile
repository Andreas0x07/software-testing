pipeline {
    agent {
        docker {
            image 'ubuntu:20.04'
            args '-u root'
        }
    }

    stages {
        stage('Setup QEMU and OpenBMC') {
            steps {
                sh '''
                # Find the latest OpenBMC image file
                IMAGE_FILE=$(ls romulus/obmc-phosphor-image-romulus-*.static.mtd | sort -V | tail -n 1)
                
                # Run QEMU with a newline to bypass the U-Boot prompt
                (echo -e "\\n" | qemu-system-arm -m 1024 -M romulus-bmc -nographic \
                    -drive file="$IMAGE_FILE",format=raw,if=mtd \
                    -net nic -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \
                    > qemu_stdout.log 2> qemu_stderr.log) &
                
                # Wait for the system to boot (adjust sleep as needed)
                sleep 30
                
                # Check if Redfish service is up (port 2443)
                if ! nc -z localhost 2443; then
                    echo "Error: Redfish service not running!"
                    exit 1
                fi
                '''
            }
        }

        stage('Run Redfish Autotests') {
            steps {
                sh '''
                export PATH=$PATH:/root/.local/bin
                python3 -m pip install --user pytest requests
                mkdir -p reports
                python3 -m pytest test_redfish.py --junitxml=reports/autotests.xml || true
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/autotests.xml'
                }
            }
        }

        stage('Run WebUI Tests') {
            steps {
                sh '''
                apt-get install -y chromium-chromedriver xvfb
                python3 -m pip install --user selenium==4.27.1 selenium-wire==5.1.0 blinker==1.6.2 html-testrunner pyvirtualdisplay
                export PATH=$PATH:/root/.local/bin
                Xvfb :99 -screen 0 1280x1024x24 &
                export DISPLAY=:99
                python3 openbmc_auth_tests.py || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/webui_test_report.html', allowEmptyArchive: true
                }
            }
        }

        stage('Run Load Tests') {
            steps {
                sh '''
                export PATH=$PATH:/root/.local/bin
                python3 -m pip install --user locust
                mkdir -p reports
                locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 1m --html reports/load_test.html || true
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'reports/load_test.html', allowEmptyArchive: true
                }
            }
        }
    }

    post {
        always {
            sh '''
            echo "Attempting to stop QEMU process..."
            pkill -f qemu-system-arm || true
            sleep 5
            pkill -9 -f qemu-system-arm || true
            echo "QEMU cleanup completed."
            '''
        }
    }
}
