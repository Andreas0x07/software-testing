pipeline {
    agent {
        docker {
            image 'ubuntu:20.04' // Or another suitable Ubuntu base
            args '-u root'        // This will run commands inside this container as root
        }
    }

    stages {
        stage('Setup QEMU and OpenBMC') {
            steps {
                sh '''
                apt-get update && apt-get install -y qemu-system-arm unzip wget
                wget -O romulus.zip "https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip" || { echo "Download failed"; exit 1; }
                unzip -o romulus.zip
                # Find the exact image file
                IMAGE_FILE=$(ls romulus/obmc-phosphor-image-romulus-*.static.mtd | head -n 1)
                if [ -z "$IMAGE_FILE" ]; then
                    echo "Error: No image file found matching romulus/obmc-phosphor-image-romulus-*.static.mtd"
                    exit 1
                fi
                # Run QEMU with the resolved file path
                qemu-system-arm -m 256 -M romulus-bmc -nographic \
                    -drive file="$IMAGE_FILE",format=raw,if=mtd \
                    -net nic -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu &
                # Wait for QEMU to be ready (check if port 2443 is open)
                for i in {1..60}; do
                    if nc -z localhost 2443; then
                        echo "QEMU is ready"
                        break
                    fi
                    echo "Waiting for QEMU to start..."
                    sleep 1
                done
                if ! nc -z localhost 2443; then
                    echo "Error: QEMU failed to start within 60 seconds"
                    exit 1
                fi
                '''
            }
        }

        stage('Run Redfish Autotests') {
            steps {
                sh '''
                pip install pytest requests
                mkdir -p reports
                pytest test_redfish.py --junitxml=reports/autotests.xml
                '''
            }
            post {
                always {
                    junit 'reports/autotests.xml'
                }
            }
        }

        stage('Run WebUI Tests') {
            steps {
                sh '''
                apt-get install -y chromium-driver  # No sudo needed due to -u root
                pip install selenium selenium-wire html-testrunner
                python3 openbmc_auth_tests.py
                '''
            }
            post {
                always {
                    archiveArtifacts artifacts: 'test_report.html', allowEmptyArchive: true
                }
            }
        }

        stage('Run Load Tests') {
            steps {
                sh '''
                pip install locust
                mkdir -p reports
                locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 1m --html reports/load_test.html
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
            sh 'pkill -f qemu-system-arm || true'
        }
    }
}
