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
                export DEBIAN_FRONTEND=noninteractive
                echo "tzdata tzdata/Areas select Etc" | debconf-set-selections
                echo "tzdata tzdata/Zones/Etc select UTC" | debconf-set-selections
                apt-get update && apt-get install -y qemu-system-arm unzip wget netcat python3 python3-pip curl
                wget -O romulus.zip "https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip" || { echo "Download failed"; exit 1; }
                unzip -o romulus.zip
                IMAGE_FILE=$(ls romulus/obmc-phosphor-image-romulus-*.static.mtd | head -n 1)
                if [ -z "$IMAGE_FILE" ]; then
                    echo "Error: No image file found matching romulus/obmc-phosphor-image-romulus-*.static.mtd"
                    exit 1
                fi
                qemu-system-arm -m 256 -M romulus-bmc -nographic \
                    -drive file="$IMAGE_FILE",format=raw,if=mtd \
                    -net nic -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu &
                for i in {1..120}; do
                    if nc -z localhost 2443 || curl -k https://localhost:2443/redfish/v1 >/dev/null 2>&1; then
                        echo "QEMU is ready"
                        break
                    fi
                    echo "Waiting for QEMU to start..."
                    sleep 2
                done
                if ! nc -z localhost 2443; then
                    echo "Error: QEMU failed to start within 240 seconds"
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
                python3 -m pip show pytest || echo "pytest installation failed"
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
                apt-get install -y chromium-chromedriver
                python3 -m pip install --user --no-cache-dir selenium==4.27.1 selenium-wire==5.1.0 blinker==1.6.2 html-testrunner
                export PATH=$PATH:/root/.local/bin
                python3 openbmc_auth_tests.py || true
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
                export PATH=$PATH:/root/.local/bin
                python3 -m pip install --user locust
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
