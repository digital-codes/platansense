#!/bin/bash
# install.sh - Quick installation script for Sensor RAG Upload Backend

set -e

echo "============================================"
echo "Sensor RAG Upload Backend - Installation"
echo "============================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

print_status "Installation directory: $SCRIPT_DIR"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_warning "Some steps may require root privileges"
    echo "You may be prompted for your password during installation"
fi

echo "============================================"
echo "Step 1: Checking System Requirements"
echo "============================================"
echo ""

# Check PHP version
print_status "Checking PHP installation..."
if command -v php &> /dev/null; then
    PHP_VERSION=$(php -r 'echo PHP_VERSION;')
    print_status "PHP found (version $PHP_VERSION)"
    
    # Check if PHP version is 8.0 or higher
    PHP_MAJOR=$(echo $PHP_VERSION | cut -d. -f1)
    if [ "$PHP_MAJOR" -lt 8 ]; then
        print_error "PHP version 8.0 or higher is required"
        exit 1
    fi
else
    print_error "PHP not found. Please install PHP 8.0 or higher"
    exit 1
fi

# Check Composer
print_status "Checking Composer installation..."
if command -v composer &> /dev/null; then
    COMPOSER_VERSION=$(composer --version | grep -oP 'Composer version \K[0-9.]+')
    print_status "Composer found (version $COMPOSER_VERSION)"
else
    print_error "Composer not found. Please install Composer"
    echo "Visit: https://getcomposer.org/download/"
    exit 1
fi

# Check for required PHP extensions
print_status "Checking required PHP extensions..."
REQUIRED_EXTENSIONS=("curl" "json" "openssl" "mbstring")
ALL_EXTENSIONS_PRESENT=true

for ext in "${REQUIRED_EXTENSIONS[@]}"; do
    if php -m | grep -q "^$ext$"; then
        print_status "Extension '$ext' is available"
    else
        print_warning "Extension '$ext' is missing"
        ALL_EXTENSIONS_PRESENT=false
    fi
done

if [ "$ALL_EXTENSIONS_PRESENT" = false ]; then
    print_error "Some required PHP extensions are missing"
    exit 1
fi

echo ""
echo "============================================"
echo "Step 2: Creating Directories"
echo "============================================"
echo ""

# Create cache and configuration directories
print_status "Creating configuration directories..."
sudo mkdir -p /var/www/files/platane
sudo chown $USER:$USER /var/www/files/platane

# Ensure audio and data directories exist
if [ ! -d "audio" ]; then
    mkdir -p audio
    print_status "Created audio directory"
else
    print_status "Audio directory already exists"
fi

if [ ! -d "data" ]; then
    mkdir -p data
    print_status "Created data directory"
else
    print_status "Data directory already exists"
fi

# Set proper permissions
chmod -R 755 audio data
print_status "Set directory permissions"

echo ""
echo "============================================"
echo "Step 3: Installing PHP Dependencies"
echo "============================================"
echo ""

print_status "Installing Composer dependencies..."
if composer install; then
    print_status "Composer dependencies installed successfully"
else
    print_error "Failed to install Composer dependencies"
    exit 1
fi

echo ""
echo "============================================"
echo "Step 4: Setting Up Configuration"
echo "============================================"
echo ""

# Create configuration file if it doesn't exist
CONFIG_FILE="/var/www/files/platane/config.ini"
if [ ! -f "$CONFIG_FILE" ]; then
    print_status "Creating configuration file..."
    
    # Generate random JWT key
    JWT_KEY=$(openssl rand -hex 32)
    
    sudo tee "$CONFIG_FILE" > /dev/null <<EOF
[JWT]
key = $JWT_KEY
relatedTo = platansense-rag-backend
issuedBy = your-organization
EOF
    print_status "Configuration file created: $CONFIG_FILE"
else
    print_status "Configuration file already exists: $CONFIG_FILE"
    print_warning "You may want to review the existing configuration"
fi

# Create devices file if it doesn't exist
DEVICES_FILE="/var/www/files/platane/devices.json"
if [ ! -f "$DEVICES_FILE" ]; then
    print_status "Creating devices file..."
    
    sudo tee "$DEVICES_FILE" > /dev/null <<EOF
{
  "sensor001": "a1b2c3d4e5f6",
  "sensor002": "f6e5d4c3b2a1"
}
EOF
    print_status "Devices file created: $DEVICES_FILE"
    print_warning "Please update the devices file with your actual sensor credentials"
else
    print_status "Devices file already exists: $DEVICES_FILE"
fi

echo ""
echo "============================================"
echo "Step 5: Checking External Dependencies"
echo "============================================"
echo ""

# Check Whisper
print_status "Checking Whisper installation..."
if command -v whisper-cli &> /dev/null; then
    WHISPER_INSTALLED=true
    print_status "Whisper CLI found"
    
    # Check if model exists
    if [ -f "/opt/whisper/models/ggml-base-q8_0.bin" ]; then
        print_status "Whisper model found"
    else
        print_warning "Whisper model not found at /opt/whisper/models/ggml-base-q8_0.bin"
        WHISPER_INSTALLED=false
    fi
else
    print_warning "Whisper CLI not found"
    WHISPER_INSTALLED=false
fi

# Check Piper
print_status "Checking Piper TTS installation..."
if [ -f "/opt/pyenvs/piper/bin/piper" ]; then
    PIPER_INSTALLED=true
    print_status "Piper TTS found"
    
    # Check if voice model exists
    if [ -f "/opt/pyenvs/piper/voices/de_DE-thorsten-low.onnx" ]; then
        print_status "Piper German voice model found"
    else
        print_warning "Piper German voice model not found"
        PIPER_INSTALLED=false
    fi
else
    print_warning "Piper TTS not found"
    PIPER_INSTALLED=false
fi

# Check Ollama
print_status "Checking Ollama installation..."
if command -v ollama &> /dev/null; then
    OLLAMA_INSTALLED=true
    print_status "Ollama found"
    
    # Check if Ollama is running
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        print_status "Ollama service is running"
    else
        print_warning "Ollama service is not running"
        OLLAMA_INSTALLED=false
    fi
    
    # Check for required model
    if $OLLAMA_INSTALLED; then
        MODELS=$(curl -s http://localhost:11434/api/tags)
        if echo "$MODELS" | grep -q "granite4.1"; then
            print_status "Required model granite4.1 found"
        else
            print_warning "Required model granite4.1 not found"
            print_warning "Pull it with: ollama pull granite4.1:3b"
            OLLAMA_INSTALLED=false
        fi
    fi
else
    print_warning "Ollama not found"
    OLLAMA_INSTALLED=false
fi

# Check ALSA
print_status "Checking ALSA audio tools..."
if command -v aplay &> /dev/null; then
    print_status "ALSA aplay found"
else
    print_warning "ALSA aplay not found - install alsa-utils"
fi

echo ""
echo "============================================"
echo "Installation Summary"
echo "============================================"
echo ""

print_status "Basic installation completed successfully!"
echo ""

if [ "$WHISPER_INSTALLED" = true ] && [ "$PIPER_INSTALLED" = true ] && [ "$OLLAMA_INSTALLED" = true ]; then
    print_status "All external dependencies are installed and configured!"
    print_status "You can now start using the system."
else
    print_warning "Some external dependencies are missing or not configured"
    echo ""
    echo "Missing components:"
    [ "$WHISPER_INSTALLED" = false ] && echo "  - Whisper: Install and configure Whisper CLI"
    [ "$PIPER_INSTALLED" = false ] && echo "  - Piper TTS: Install and configure Piper TTS"
    [ "$OLLAMA_INSTALLED" = false ] && echo "  - Ollama: Install, start, and pull the required model"
    echo ""
    echo "Please install the missing dependencies to use the full functionality."
fi

echo ""
echo "============================================"
echo "Next Steps"
echo "============================================"
echo ""

echo "1. Review and update configuration:"
echo "   $CONFIG_FILE"
echo "   $DEVICES_FILE"
echo ""

echo "2. Run the test suite:"
echo "   php testRagPipeline.php"
echo "   ./test_pipeline_commands.sh"
echo ""

echo "3. Start using the system (see QUICKSTART.md for details)"
echo ""

echo "4. For more information, see:"
echo "   - README.md (comprehensive documentation)"
echo "   - QUICKSTART.md (quick start guide)"
echo "   - CONFIGURATION.md (configuration examples)"
echo ""

echo "============================================"
echo "Installation Complete!"
echo "============================================"