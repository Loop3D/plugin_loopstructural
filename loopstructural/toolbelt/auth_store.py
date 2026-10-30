"""Keep a secret (a token) in the QGIS authentication database, not in plain text.

The plugin settings keep only the id of the authentication configuration.
QGIS can ask for its master password the first time.
"""

from qgis.core import QgsApplication, QgsAuthMethodConfig

from .preferences import PlgOptionsManager

_METHOD = 'Basic'
_USER = 'loopstructural'


def load_secret(id_key: str) -> str:
    """Return the secret of the configuration whose id is in the setting `id_key`."""
    config_id = PlgOptionsManager.get_value_from_key(id_key, '', str)
    if not config_id:
        return ''
    config = QgsAuthMethodConfig()
    result = QgsApplication.authManager().loadAuthenticationConfig(config_id, config, True)
    # some QGIS versions return (ok, config)
    if isinstance(result, tuple):
        ok, config = result
    else:
        ok = result
    return config.config('password', '') if ok else ''


def save_secret(id_key: str, name: str, secret: str) -> bool:
    """Keep `secret` in the configuration `name`, and its id in the setting `id_key`.

    An empty secret removes the configuration.
    """
    manager = QgsApplication.authManager()
    config_id = PlgOptionsManager.get_value_from_key(id_key, '', str)
    if not secret:
        if config_id:
            manager.removeAuthenticationConfig(config_id)
        PlgOptionsManager.set_value_from_key(id_key, '')
        return True
    config = QgsAuthMethodConfig(_METHOD)
    config.setName(name)
    config.setConfig('username', _USER)
    config.setConfig('password', secret)
    if config_id and config_id in manager.configIds():
        config.setId(config_id)
        ok = manager.updateAuthenticationConfig(config)
    else:
        result = manager.storeAuthenticationConfig(config)
        if isinstance(result, tuple):
            ok, config = result
        else:
            ok = result
    if ok:
        PlgOptionsManager.set_value_from_key(id_key, config.id())
    return bool(ok)
