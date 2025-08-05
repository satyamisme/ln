#!/bin/bash
cd $(dirname $0)

# The following lines are commented out as they are redundant.
# The Dockerfile handles the installation of requirements in a virtual environment.
# sudo apt install python3 python3-pip
# echo yes | pip3 install -r requirements-cli.txt
# echo yes | pip3 install -r requirements.txt

echo "Pruning stopped containers..."
echo yes | sudo docker container prune

# The Docker daemon should ideally be managed by the system's service manager (e.g., systemd).
# This line is commented out to prevent errors if the daemon is already running.
# sudo dockerd

echo "Building Docker image..."
sudo docker build . -t leech

echo "Running Docker container..."
sudo docker run --env-file config.env -p 52:52 leech
