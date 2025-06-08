#!/bin/bash

# Test script for Ollama integration
# This script helps set up and test the Ollama integration

set -e

echo "🚀 Git Smart Squash - Ollama Integration Test Setup"
echo "=================================================="

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama is not installed"
    echo "📥 Install Ollama from: https://ollama.ai/"
    echo "   Or run: curl -fsSL https://ollama.ai/install.sh | sh"
    exit 1
fi

echo "✅ Ollama is installed"

# Check if Ollama server is running
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "🔄 Starting Ollama server..."
    echo "💡 If this hangs, run 'ollama serve' in another terminal"
    
    # Try to start Ollama server in background
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    echo "⏳ Waiting for Ollama server to start..."
    sleep 5
    
    # Check if server started
    if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "❌ Failed to start Ollama server"
        echo "📝 Manual setup required:"
        echo "   1. Run 'ollama serve' in another terminal"
        echo "   2. Run 'ollama pull devstral' to download the model"
        echo "   3. Run this script again"
        kill $OLLAMA_PID 2>/dev/null || true
        exit 1
    fi
fi

echo "✅ Ollama server is running"

# Check if devstral model is available
echo "🔍 Checking for devstral model..."
MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    models = [m['name'] for m in data.get('models', [])]
    print(','.join(models))
except:
    print('')
")

if [[ $MODELS == *"devstral"* ]]; then
    echo "✅ devstral model is available"
else
    echo "📥 devstral model not found. Available models: $MODELS"
    echo "🔄 Downloading devstral model (this may take a few minutes)..."
    
    if ollama pull devstral; then
        echo "✅ devstral model downloaded successfully"
    else
        echo "❌ Failed to download devstral model"
        echo "💡 Try manually: ollama pull devstral"
        echo "💡 Or use a different model like 'llama2' or 'codellama'"
        exit 1
    fi
fi

# Test token limit functionality
echo ""
echo "🧪 Running token limit tests..."
python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider
from git_smart_squash.simple_config import Config, AIConfig

config = Config(ai=AIConfig(provider='local', model='devstral'))
provider = UnifiedAIProvider(config)

# Test token estimation
short_text = 'Hello world'
long_text = 'This is a test ' * 1000
print(f'Short text tokens: {provider._estimate_tokens(short_text)}')
print(f'Long text tokens: {provider._estimate_tokens(long_text)}')

# Test parameter calculation
params = provider._calculate_ollama_params(long_text)
print(f'Calculated params for long text: {params}')
print('✅ Token limit functionality working')
"

# Test basic Ollama connectivity
echo ""
echo "🧪 Testing Ollama connectivity..."
python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
from git_smart_squash.ai.providers.simple_unified import UnifiedAIProvider
from git_smart_squash.simple_config import Config, AIConfig

config = Config(ai=AIConfig(provider='local', model='devstral'))
provider = UnifiedAIProvider(config)

try:
    response = provider._generate_local('Say hello in one word.')
    if response and len(response.strip()) > 0:
        print(f'✅ Ollama response: {response.strip()}')
        print('✅ Ollama integration working!')
    else:
        print('❌ Empty response from Ollama')
except Exception as e:
    print(f'❌ Ollama test failed: {e}')
"

# Run the full integration test suite
echo ""
echo "🧪 Running full integration test suite..."
python3 test_ollama_integration.py

echo ""
echo "🎉 Ollama integration test complete!"
echo ""
echo "📋 Next steps:"
echo "   1. Test with a real git repository: cd /path/to/your/repo && git-smart-squash --dry-run"
echo "   2. For large repositories, the tool will automatically adjust token limits"
echo "   3. Monitor response quality and token usage in the console output"
echo ""
echo "🔧 Troubleshooting:"
echo "   - If responses are truncated, the tool will show a warning"
echo "   - Token limits are capped at 12,000 for both context and prediction"
echo "   - Large diffs will automatically use higher timeouts (up to 120 seconds)"