"""Base machinery for typed configuration dataclasses.

Each config section mirrors one of the legacy input dictionaries. The legacy dict keys
contain spaces (e.g. ``"Range Mission"``) which are not valid Python identifiers, so each
dataclass declares a ``_KEY_MAP`` mapping ``field_name -> "Dict Key"``.

The :class:`DictConfig` mixin provides faithful, lossless conversion:

* :meth:`to_dict` reproduces exactly the legacy dict (omitting fields left as ``None``),
  so existing subsystems consume it unchanged.
* :meth:`from_dict` parses a legacy dict back into the typed object.

The round-trip contract ``Cfg.from_dict(d).to_dict() == d`` is enforced by tests for the
canonical sample configurations, guaranteeing the adapter shim is behavior-preserving.
"""

from dataclasses import dataclass, fields


class ConfigError(ValueError):
    """Raised when a configuration value fails validation."""


@dataclass
class DictConfig:
    """Mixin giving dataclasses lossless (de)serialization to the legacy dict format."""

    #: Maps dataclass field name -> legacy dict key. Fields absent from the map use
    #: their own name as the key.
    _KEY_MAP: dict = None

    @classmethod
    def _key_map(cls):
        return getattr(cls, "_KEY_MAP", None) or {}

    @classmethod
    def _field_for_key(cls, key):
        for field_name, dict_key in cls._key_map().items():
            if dict_key == key:
                return field_name
        return key

    def to_dict(self):
        """Return the legacy dict, omitting fields that are ``None``.

        Nested values exposing their own ``to_dict`` are recursed into.
        """
        key_map = self._key_map()
        out = {}
        for f in fields(self):
            if f.name.startswith("_"):
                continue
            value = getattr(self, f.name)
            if value is None:
                continue
            out[key_map.get(f.name, f.name)] = _serialize(value)
        return out

    @classmethod
    def from_dict(cls, data):
        """Build the config from a legacy dict (ignores unknown keys gracefully)."""
        if data is None:
            return None
        valid = {f.name for f in fields(cls) if not f.name.startswith("_")}
        kwargs = {}
        for key, value in data.items():
            field_name = cls._field_for_key(key)
            if field_name in valid:
                kwargs[field_name] = value
        return cls(**kwargs)


def _serialize(value):
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize(v) for v in value]
    return value
