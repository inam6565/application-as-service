# setup_compute_node.sh
#!/bin/bash

echo "🚀 Setting up Compute Node VM..."

# Update system
sudo apt-get update
sudo apt-get upgrade -y

# Install Docker
echo "📦 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker

# Install Python
echo "🐍 Installing Python..."
sudo apt-get install -y python3 python3-pip python3-venv

# Create runtime agent user
echo "👤 Creating runtime-agent user..."
sudo useradd -r -s /bin/bash -m runtime-agent
sudo usermod -aG docker runtime-agent

# Create directory
echo "📁 Setting up application directory..."
sudo mkdir -p /opt/runtime-agent
sudo chown runtime-agent:runtime-agent /opt/runtime-agent

# Create virtual environment
echo "🔧 Setting up Python environment..."
sudo -u runtime-agent python3 -m venv /opt/runtime-agent/venv
sudo -u runtime-agent /opt/runtime-agent/venv/bin/pip install --upgrade pip

echo "✅ Compute node setup complete!"
echo ""
echo "Next steps:"
echo "1. Copy runtime agent files to /opt/runtime-agent/"
echo "2. Install dependencies: sudo -u runtime-agent /opt/runtime-agent/venv/bin/pip install -r requirements.txt"
echo "3. Start service: sudo systemctl start runtime-agent"