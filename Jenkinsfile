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
                
                echo "Downloading OpenBMC image..."
                wget -O romulus.zip "https://jenkins.openbmc.org/job/ci-openbmc/lastSuccessfulBuild/distro=ubuntu,label=docker-builder,target=romulus/artifact/openbmc/build/tmp/deploy/images/romulus/*zip*/romulus.zip" || { echo "Download failed"; exit 1; }
                unzip -o romulus.zip
                
                IMAGE_FILE=$(ls romulus/obmc-phosphor-image-romulus-*.static.mtd | head -n 1)
                if [ -z "$IMAGE_FILE" ]; then
                    echo "Error: No image file found matching romulus/obmc-phosphor-image-romulus-*.static.mtd"
                    exit 1
                fi
                echo "Starting QEMU with image: $IMAGE_FILE"
                
                # Redirect QEMU output to files
                qemu-system-arm -m 1024 -M romulus-bmc -nographic \
                    -drive file="$IMAGE_FILE",format=raw,if=mtd \
                    -net nic -net user,hostfwd=tcp::2222-:22,hostfwd=tcp::2443-:443,hostfwd=udp::2623-:623,hostname=qemu \
                    > qemu_stdout.log 2> qemu_stderr.log &
                
                QEMU_PID=$!
                echo "QEMU started with PID $QEMU_PID. Waiting for it to become accessible..."
                
                REDFISH_READY=0
                for i in {1..180}; do # Loop for up to 6 minutes (180 * 2s)
                    echo "Waiting for QEMU (Attempt $i/180)..."
                    # Check if port is open first
                    if nc -z localhost 2443; then
                        echo "Port 2443 is open. Checking Redfish service readiness..."
                        # Try to curl the Redfish endpoint, looking for a 200 OK or any JSON response
                        if curl --connect-timeout 10 -k -s -o /dev/null -w "%{http_code}" https://localhost:2443/redfish/v1 | grep -E "200|401|403|500"; then
                            echo "Redfish service at https://localhost:2443/redfish/v1 responded."
                            REDFISH_READY=1
                            break
                        else
                            echo "Redfish service not yet responding with expected HTTP code, or curl failed."
                        fi
                    else
                        echo "Port 2443 not yet open."
                    fi
                    # Check if QEMU process is still running
                    if ! ps -p $QEMU_PID > /dev/null; then
                        echo "QEMU process $QEMU_PID is no longer running. Aborting wait."
                        cat qemu_stderr.log # Print QEMU stderr if it died
                        exit 1
                    fi
                    sleep 2
                done

                if [ "$REDFISH_READY" -eq "0" ]; then
                    echo "Error: OpenBMC Redfish service failed to become ready within the timeout."
                    echo "Last 50 lines of QEMU stdout:"
                    tail -n 50 qemu_stdout.log || echo "qemu_stdout.log not found or empty"
                    echo "Last 50 lines of QEMU stderr:"
                    tail -n 50 qemu_stderr.log || echo "qemu_stderr.log not found or empty"
                    exit 1
                fi
                
                echo "OpenBMC Redfish service appears ready. Giving an additional 30 seconds for full stabilization..."
                sleep 30 
                echo "Presuming OpenBMC services are now fully stable."
                '''
            }
            post {
                always {
                    // Archive QEMU logs
                    archiveArtifacts artifacts: 'qemu_stdout.log, qemu_stderr.log', allowEmptyArchive: true
                }
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
                apt-get install -y chromium-chromedriver xvfb # xvfb for truly headless
                python3 -m pip install --user --no-cache-dir selenium==4.27.1 selenium-wire==5.1.0 blinker==1.6.2 html-testrunner pyvirtualdisplay
                export PATH=$PATH:/root/.local/bin
                # Start xvfb for headless operation
                # Xvfb :99 -screen 0 1280x1024x24 &
                # export DISPLAY=:99
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
    } // End of stages

    post {
        always {
            sh '''
            echo "Attempting to stop QEMU process..."
            # Try to kill QEMU gracefully then forcefully
            pkill -f qemu-system-arm && sleep 5
            pkill -9 -f qemu-system-arm || echo "QEMU process not found or already killed."
            echo "QEMU cleanup attempted."
            '''
        }
    }
}
