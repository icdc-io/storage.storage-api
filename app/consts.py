"""
Generate global variables from config and ENV
- from ENV 'LISTEN_PORT'
- from config.yaml:
  listen:
    port:
"""

import os

import yaml

from app.loggers import log

# NOTE: can use only log.info() level or higher, as real LOG_LEVEL is not loaded yet from configs

def __defaults(file_name, directory_name):
    # /opt/app/config is a mounted ConfigMap directory with all configs
    file_name = os.path.join(os.getcwd(), directory_name, file_name)
    if not os.path.exists(file_name):
        log.info(f"Config file {file_name} not found. Skipping it.")
        return {}
    with open(file_name, encoding="utf-8") as file_handle:
        return yaml.load(file_handle, Loader=yaml.FullLoader)


def __set_consts(base, config):
    """
    Sets constants based on the configuration file.

    Parameters:
        base (str): The base key for the constants. If provided, it is prefixed to each key in the configuration file.
        config (dict): A dictionary containing key-value pairs for the constants. When setting values, it
        is checked whether an environment variable with the same name exists (os.getenv(full_key, value)).
        If exists, then the value from the environment is used. Otherwise - from the configuration file.

    Returns:
        None
    """
    for key, value in config.items():
        full_key = (f"{base}_{key}" if base else key).upper()

        if isinstance(value, dict):
            globals()[full_key] = value
            __set_consts(full_key, value)
        else:
            # Resolve references to other constants
            if isinstance(value, str) and "{" in value:
                try:
                    value = value.format(**globals())
                except KeyError:
                    log.warning(
                        f"Error resolving constant {full_key} with value '{value}'. Skipping."
                    )
            globals()[full_key] = os.getenv(full_key, value)


def config() -> None:
    """
    Generate consts from config.yaml or env file.

    This function reads the configuration from a YAML file or an environment file,
    sets the constants using the configuration, and prints the values of the constants.

    Args:
        None

    Returns:
        None
    """
    # Log the start of the configuration process
    log.info("Starting config...")

    # Read the configuration from the YAML files or environment variables
    __set_consts("", __defaults("config.yaml", "config"))

    __set_consts("", __defaults("rbac.yaml", "settings"))

    # Backward compatibility with old config
    if 'OPERATOR_GROUP' not in globals():
        globals()['OPERATOR_GROUP'] = globals()['LOCATION_ADMIN_GROUP']

    # Print the values of the constants
    for key, value in globals().items():
        if key.isupper():
            log.info(f"{key} = {value}")

    # Log the completion of the configuration process
    log.info("Config completed.")


config()

def get(key, default=None):
    return globals().get(key, default)
