"""Tests for configuration management."""

import pytest
import tempfile
import os
import yaml
from git_smart_squash.config import ConfigManager
from git_smart_squash.models import Config, GroupingConfig, AIConfig


class TestConfigManager:
    """Test cases for ConfigManager."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_manager = ConfigManager()
    
    def test_load_default_config(self):
        """Test loading default configuration."""
        config = self.config_manager.load_config()
        
        assert isinstance(config, Config)
        assert config.grouping.time_window == 1800
        assert config.ai.provider == "openai"
        assert config.output.dry_run_default is True
    
    def test_load_config_from_file(self):
        """Test loading configuration from a YAML file."""
        config_data = {
            'grouping': {
                'time_window': 3600,
                'min_file_overlap': 2,
                'similarity_threshold': 0.8
            },
            'ai': {
                'provider': 'anthropic',
                'model': 'claude-3-sonnet-20240229'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            config = self.config_manager.load_config(config_path)
            
            assert config.grouping.time_window == 3600
            assert config.grouping.min_file_overlap == 2
            assert config.grouping.similarity_threshold == 0.8
            assert config.ai.provider == 'anthropic'
            assert config.ai.model == 'claude-3-sonnet-20240229'
        finally:
            os.unlink(config_path)
    
    def test_load_config_file_not_found(self):
        """Test loading configuration from non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.config_manager.load_config("non_existent_config.yml")
    
    def test_load_config_invalid_yaml(self):
        """Test loading configuration from invalid YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("invalid: yaml: content: [\n")
            config_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Invalid YAML"):
                self.config_manager.load_config(config_path)
        finally:
            os.unlink(config_path)
    
    def test_save_config(self):
        """Test saving configuration to file."""
        config = Config()
        config.grouping.time_window = 7200
        config.ai.provider = "local"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            config_path = f.name
        
        try:
            self.config_manager.save_config(config, config_path)
            
            # Verify file was created and contains correct data
            assert os.path.exists(config_path)
            
            with open(config_path, 'r') as f:
                saved_data = yaml.safe_load(f)
            
            assert saved_data['grouping']['time_window'] == 7200
            assert saved_data['ai']['provider'] == "local"
        finally:
            if os.path.exists(config_path):
                os.unlink(config_path)
    
    def test_create_default_config(self):
        """Test creating default configuration file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "test-config.yml")
            
            created_path = self.config_manager.create_default_config(config_path)
            
            assert created_path == config_path
            assert os.path.exists(config_path)
            
            # Verify the created config can be loaded
            loaded_config = self.config_manager.load_config(config_path)
            assert isinstance(loaded_config, Config)
    
    def test_validate_config_valid(self):
        """Test validation of valid configuration."""
        config = Config()
        result = self.config_manager.validate_config(config)
        assert result is True
    
    def test_validate_config_invalid_time_window(self):
        """Test validation with invalid time window."""
        config = Config()
        config.grouping.time_window = -100
        
        with pytest.raises(ValueError, match="time_window must be positive"):
            self.config_manager.validate_config(config)
    
    def test_validate_config_invalid_similarity_threshold(self):
        """Test validation with invalid similarity threshold."""
        config = Config()
        config.grouping.similarity_threshold = 1.5
        
        with pytest.raises(ValueError, match="similarity_threshold must be between 0.5 and 0.95"):
            self.config_manager.validate_config(config)
    
    def test_validate_config_invalid_provider(self):
        """Test validation with invalid AI provider."""
        config = Config()
        config.ai.provider = "invalid_provider"
        
        with pytest.raises(ValueError, match="ai.provider must be one of"):
            self.config_manager.validate_config(config)
    
    def test_validate_config_empty_types(self):
        """Test validation with empty commit types."""
        config = Config()
        config.commit_format.types = []
        
        with pytest.raises(ValueError, match="commit_format.types cannot be empty"):
            self.config_manager.validate_config(config)