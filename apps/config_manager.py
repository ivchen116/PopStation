import ujson as json
import os

class ConfigManager:
    _instance = None
    _config_file = "config.json"

    _default_config = {
        "volume": 10,
        "tts_enable": True,
        "players": ["Ciya", "Qiang"],
        "ball_bgcolors": [0x07E0, 0x001F], #GREEN, BLUE
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._config = {}
            cls._instance._dirty = False
            cls._instance._load()
        return cls._instance

    def _load(self):
        try:
            if self._config_file in os.listdir():
                with open(self._config_file, "r") as f:
                    self._config = json.load(f)
            else:
                self._config = self._default_config.copy()
                self._dirty = True
        except Exception as e:
            print("Config load error:", e)
            self._config = self._default_config.copy()
            self._dirty = True

        #if self._dirty:
        #    self.save()

    def save(self):
        if not self._dirty:
            return

        try:
            with open(self._config_file, "w") as f:
                json.dump(self._config, f)
            self._dirty = False 
        except Exception as e:
            print("Config save error:", e)

    def get(self, key):
        return self._config.get(key, self._default_config.get(key))

    def set(self, key, value):
        old = self._config.get(key)

        if old != value:
            self._config[key] = value
            self._dirty = True

    def get_all(self):
        return self._config

    def reset(self):
        self._config = self._default_config.copy()
        self._dirty = True
