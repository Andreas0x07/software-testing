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
                echo "Starting QEMU with image: $IMAGE_FILE"
                # Increased memory to 1024M
                qemu-system-arm -m 1024 -M romulus-bmc -nographic \
                    -drive file="$IMAGE_FILE",format=raw,if=mtd \
                    -net nic -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu &
                
                echo "Waiting for QEMU to become accessible..."
                for i in {1..150}; do # Increased loop for up to 300 seconds
                    # Check if port 2443 is listening OR if the Redfish service endpoint gives any response (even an error)
                    if nc -z localhost 2443 || curl --connect-timeout 5 -k https://localhost:2443/redfish/v1 >/dev/null 2>&1; then
                        echo "QEMU port 2443 is open or Redfish service is responding."
                        break
                    fi
                    echo "Waiting for QEMU (Attempt $i/150)..."
                    sleep 2
                done

                if ! nc -z localhost 2443; then # Final check on port
                    echo "Error: QEMU port 2443 failed to become open within 300 seconds."
                    # Attempt to get QEMU logs if possible (advanced, might need to redirect QEMU output to a file)
                    ps aux | grep qemu-system-arm
                    exit 1
                fi
                
                echo "QEMU port 2443 is open. Giving extra 45 seconds for services to stabilize..."
                sleep 45 
                echo "Presuming OpenBMC services are now stable."
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
                # Ensure chromedriver from apt is in PATH or accessible
                # If issues persist, try: export CHROMEDRIVER_PATH=$(which chromedriver)
                # echo "Chromedriver path: $CHROMEDRIVER_PATH"
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
                locust -f locustfile.py --headless --users 10 --spawn-rate 2 --run-time 1m --html reports/load_test.html || echo "Locust tests completed or failed"
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
            pkill -f qemu-system-arm || echo "QEMU process not found or already killed."
            echo "QEMU cleanup attempted."
            '''
        }
    }
}
