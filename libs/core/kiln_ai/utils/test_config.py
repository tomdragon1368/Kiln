import os
import pwd
from unittest.mock import patch

import pytest
import yaml

from libs.core.kiln_ai.utils.config import Config, ConfigProperty, _get_user_id


# mock out the settings path so we don't clobber the user's actual settings
@pytest.fixture(autouse=True)
def use_temp_settings_dir(tmp_path):
    with patch.object(
        Config, "settings_path", return_value=str(tmp_path / "settings.yaml")
    ):
        yield


@pytest.fixture
def mock_yaml_file(tmp_path):
    yaml_file = tmp_path / "test_settings.yaml"
    return str(yaml_file)


@pytest.fixture
def config_with_yaml(mock_yaml_file):
    with patch(
        "libs.core.kiln_ai.utils.config.Config.settings_path",
        return_value=mock_yaml_file,
    ):
        yield Config(
            properties={
                "example_property": ConfigProperty(
                    str, default="default_value", env_var="EXAMPLE_PROPERTY"
                ),
                "int_property": ConfigProperty(int, default=0),
            }
        )


@pytest.fixture
def reset_config():
    Config._shared_instance = None
    yield
    Config._shared_instance = None


def test_shared_instance(reset_config):
    config1 = Config.shared()
    config2 = Config.shared()
    assert config1 is config2


def test_property_default_value(reset_config, config_with_yaml):
    config = config_with_yaml
    assert config.example_property == "default_value"


def test_property_env_var(reset_config, config_with_yaml):
    os.environ["EXAMPLE_PROPERTY"] = "env_value"
    config = config_with_yaml
    assert config.example_property == "env_value"
    del os.environ["EXAMPLE_PROPERTY"]


def test_property_setter(reset_config, config_with_yaml):
    config = config_with_yaml
    config.example_property = "new_value"
    assert config.example_property == "new_value"


def test_nonexistent_property(reset_config, config_with_yaml):
    config = config_with_yaml
    with pytest.raises(AttributeError):
        config.nonexistent_property


def test_property_type_conversion(reset_config):
    Config._shared_instance = None

    config = Config(properties={"int_property": ConfigProperty(int, default="42")})
    assert isinstance(config.int_property, int)
    assert config.int_property == 42


def test_property_priority(reset_config, config_with_yaml):
    os.environ["EXAMPLE_PROPERTY"] = "env_value"
    config = config_with_yaml

    # Environment variable takes precedence over default
    assert config.example_property == "env_value"

    # Setter takes precedence over environment variable
    config.example_property = "new_value"
    assert config.example_property == "new_value"

    del os.environ["EXAMPLE_PROPERTY"]


def test_lazy_loading(reset_config, config_with_yaml):
    config = config_with_yaml
    assert "example_property" not in config._values
    _ = config.example_property
    assert "example_property" in config._values


def test_default_lambda(reset_config):
    Config._shared_instance = None

    def default_lambda():
        return "lambda_value"

    config = Config(
        properties={
            "lambda_property": ConfigProperty(str, default_lambda=default_lambda)
        }
    )

    assert config.lambda_property == "lambda_value"

    # Test that the lambda is only called once
    assert "lambda_property" in config._values
    config._properties["lambda_property"].default_lambda = lambda: "new_lambda_value"
    assert config.lambda_property == "lambda_value"


def test_get_user_id_none(monkeypatch):
    def mock_getpwuid(_):
        class MockPwnam:
            pw_name = None

        return MockPwnam()

    monkeypatch.setattr(pwd, "getpwuid", mock_getpwuid)
    assert _get_user_id() == "unknown_user"


def test_get_user_id_exception(monkeypatch):
    def mock_getpwuid(_):
        raise Exception("Test exception")

    monkeypatch.setattr(pwd, "getpwuid", mock_getpwuid)
    assert _get_user_id() == "unknown_user"


def test_get_user_id_valid(monkeypatch):
    def mock_getpwuid(_):
        class MockPwnam:
            pw_name = "test_user"

        return MockPwnam()

    monkeypatch.setattr(pwd, "getpwuid", mock_getpwuid)
    assert _get_user_id() == "test_user"


def test_user_id_default(reset_config):
    config = Config()
    # assert config.user_id == "scosman"
    assert len(config.user_id) > 0


def test_autosave_examples_default(reset_config):
    config = Config()
    assert config.autosave_examples


def test_yaml_persistence(config_with_yaml, mock_yaml_file):
    # Set a value
    config_with_yaml.example_property = "yaml_value"

    # Check that the value was saved to the YAML file
    with open(mock_yaml_file, "r") as f:
        saved_settings = yaml.safe_load(f)
    assert saved_settings["example_property"] == "yaml_value"

    # Create a new config instance to test loading from YAML
    new_config = Config(
        properties={
            "example_property": ConfigProperty(
                str, default="default_value", env_var="EXAMPLE_PROPERTY"
            ),
        }
    )

    # Check that the value is loaded from YAML
    assert new_config.example_property == "yaml_value"

    # Set an environment variable to check that yaml takes priority
    os.environ["EXAMPLE_PROPERTY"] = "env_value"

    # Check that the YAML value takes priority
    assert new_config.example_property == "yaml_value"

    # Clean up the environment variable
    del os.environ["EXAMPLE_PROPERTY"]


def test_yaml_type_conversion(config_with_yaml, mock_yaml_file):
    # Set an integer value
    config_with_yaml.int_property = 42

    # Check that the value was saved to the YAML file
    with open(mock_yaml_file, "r") as f:
        saved_settings = yaml.safe_load(f)
    assert saved_settings["int_property"] == 42

    # Create a new config instance to test loading and type conversion from YAML
    new_config = Config(
        properties={
            "int_property": ConfigProperty(int, default=0),
        }
    )

    # Check that the value is loaded from YAML and converted to int
    assert new_config.int_property == 42
    assert isinstance(new_config.int_property, int)
