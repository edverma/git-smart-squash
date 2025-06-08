# Ollama Integration and Token Management

This document describes the enhanced Ollama integration with intelligent token management and comprehensive integration testing.

## Overview

The tool now includes sophisticated token limit handling and real-world integration tests that verify the AI model behaves correctly with actual Ollama server responses.

## Token Management Features

### Automatic Token Calculation
- **Estimation**: Uses heuristic-based token counting (1 token ≈ 4 characters)
- **Context Sizing**: Automatically calculates `num_ctx` based on prompt size + safety buffer
- **Prediction Limits**: Sets `num_predict` based on expected response size
- **Hard Caps**: Both `num_ctx` and `num_predict` are capped at 12,000 tokens

### Dynamic Parameter Adjustment
```python
# Small prompt example
prompt = "Analyze this small diff..."
params = {
    "num_ctx": 2000,    # prompt tokens + buffer
    "num_predict": 2000  # expected response size
}

# Large prompt example  
prompt = "Analyze this massive diff..." * 1000
params = {
    "num_ctx": 12000,    # capped at maximum
    "num_predict": 2000  # reasonable for JSON response
}
```

### Enhanced Error Handling
- **Timeout Scaling**: 60s for normal requests, 120s for large contexts
- **Truncation Detection**: Warns when responses may be incomplete
- **Response Validation**: Validates JSON structure and content quality

## Integration Testing

### Test Categories

#### 1. Server Availability Tests
- Verifies Ollama server is running on localhost:11434
- Checks devstral model availability
- Validates API connectivity

#### 2. Token Limit Tests
- Tests token estimation accuracy
- Verifies parameter calculation for various prompt sizes
- Ensures hard caps are enforced

#### 3. Real AI Response Tests
- Tests simple commit organization prompts
- Tests complex multi-file diffs
- Tests large diff handling with token limits
- Validates response structure and quality

#### 4. CLI Integration Tests
- End-to-end workflow testing with real Ollama
- Dry-run validation
- Response quality assessment

### Running Integration Tests

#### Quick Setup
```bash
# Run the automated setup and test script
./test_with_ollama.sh
```

#### Manual Setup
```bash
# 1. Start Ollama server
ollama serve

# 2. Download devstral model
ollama pull devstral

# 3. Run integration tests
python3 test_ollama_integration.py
```

### Test Results Interpretation

#### Expected Outputs
- **Token Estimation**: Should scale linearly with text length
- **Parameter Calculation**: Should respect hard caps
- **AI Responses**: Should contain structured commit suggestions
- **CLI Integration**: Should complete without errors in dry-run mode

#### Common Issues
- **Server Not Running**: Tests will skip if Ollama is unavailable
- **Model Not Found**: Tests will skip if devstral is not downloaded
- **Timeout Errors**: Expected for very large diffs (>10,000 tokens)
- **Response Quality**: AI should mention relevant keywords from the diff

## Token Limit Implementation Details

### Current Implementation
```python
class UnifiedAIProvider:
    MAX_CONTEXT_TOKENS = 12000
    MAX_PREDICT_TOKENS = 12000
    
    def _calculate_ollama_params(self, prompt: str) -> dict:
        prompt_tokens = self._estimate_tokens(prompt)
        context_needed = prompt_tokens + 1000  # Safety buffer
        num_ctx = min(context_needed, self.MAX_CONTEXT_TOKENS)
        num_predict = min(2000, self.MAX_PREDICT_TOKENS)
        
        return {
            "num_ctx": num_ctx,
            "num_predict": num_predict
        }
```

### Request Options
The enhanced Ollama integration now sends:
```json
{
    "model": "devstral",
    "prompt": "...",
    "stream": false,
    "options": {
        "num_ctx": 8000,      // Dynamic based on prompt
        "num_predict": 2000,   // Fixed for commit responses
        "temperature": 0.7,    // Balanced creativity
        "top_p": 0.9,         // Nucleus sampling
        "top_k": 40           // Top-k sampling
    }
}
```

## Performance Characteristics

### Token Usage Patterns
- **Small diffs** (<1000 lines): ~2000-4000 context tokens
- **Medium diffs** (1000-5000 lines): ~4000-8000 context tokens  
- **Large diffs** (>5000 lines): 12000 context tokens (capped)

### Response Times
- **Small requests**: 5-15 seconds
- **Medium requests**: 15-45 seconds
- **Large requests**: 45-120 seconds (with timeout protection)

### Memory Usage
- **Context window**: Up to 12,000 tokens (~48KB of text)
- **Model memory**: Depends on devstral model size (~4-7GB)
- **Request overhead**: Minimal (~1-2MB per request)

## Troubleshooting

### Token Limit Issues
```bash
# If responses are truncated
Warning: Response may have been truncated. Used 12000 context tokens.

# Solutions:
1. Break large changes into smaller commits manually
2. Use --base with a more recent branch
3. Consider using a model with larger context window
```

### Performance Issues
```bash
# If requests timeout
Local AI generation failed: Ollama request timed out after 120 seconds

# Solutions:
1. Reduce diff size by committing intermediate changes
2. Use faster model (if available)
3. Increase timeout in extreme cases
```

### Quality Issues
```bash
# If AI responses are poor quality
1. Ensure model is warmed up (run a test query first)
2. Check that devstral model is fully downloaded
3. Verify diff contains meaningful changes
4. Try with smaller, focused diffs first
```

## Future Enhancements

### Potential Improvements
1. **Adaptive Tokenization**: Use tiktoken for more accurate counting
2. **Context Compression**: Summarize large diffs before analysis
3. **Model Selection**: Auto-detect optimal model based on context size
4. **Streaming Responses**: Handle partial responses for very large contexts
5. **Quality Metrics**: Measure and report response quality scores

### Configuration Options
Consider adding these config options:
```yaml
ai:
  provider: local
  model: devstral
  token_limits:
    max_context: 12000      # Override default
    max_predict: 2000       # Override default
    timeout: 120           # Override timeout
  quality:
    min_response_length: 100
    require_json: true
```

## Testing Strategy

### Continuous Integration
The integration tests are designed to:
1. **Skip gracefully** when Ollama is not available
2. **Test offline functionality** (token calculation, parameter logic)
3. **Validate real responses** when Ollama is running
4. **Measure performance** and detect regressions

### Local Development
For developers working on the AI integration:
1. Run `./test_with_ollama.sh` for full setup and testing
2. Use `python3 test_ollama_integration.py` for quick validation
3. Monitor token usage and response quality during development
4. Test with repositories of different sizes

This comprehensive approach ensures the AI integration is robust, performant, and reliable across different usage scenarios.