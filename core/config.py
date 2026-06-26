import json
import os
import sys
import base64
import hashlib
import bcrypt

if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.dirname(sys.executable)
else:
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(_BASE_DIR, "analyzer_config.json")
_SECRET_FILE = os.path.join(_BASE_DIR, ".secret_key")


class CryptoManager:
    """Config degerlerini sifreleme/cozme (XOR + base64)"""
    _key = None

    @classmethod
    def _get_key(cls):
        if cls._key:
            return cls._key
        if os.path.exists(_SECRET_FILE):
            with open(_SECRET_FILE, "rb") as f:
                cls._key = f.read()
        else:
            cls._key = os.urandom(32)
            with open(_SECRET_FILE, "wb") as f:
                f.write(cls._key)
        return cls._key

    @classmethod
    def encrypt(cls, plaintext):
        if not plaintext:
            return ""
        key = cls._get_key()
        data = plaintext.encode("utf-8")
        encrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return base64.b64encode(encrypted).decode("ascii")

    @classmethod
    def decrypt(cls, ciphertext):
        if not ciphertext:
            return ""
        try:
            key = cls._get_key()
            data = base64.b64decode(ciphertext)
            decrypted = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
            return decrypted.decode("utf-8")
        except:
            return ciphertext


class ConfigManager:
    @staticmethod
    def save_mic_index(index):
        config = ConfigManager._load_config()
        config["mic_index"] = index
        ConfigManager._save_config(config)

    @staticmethod
    def load_mic_index():
        config = ConfigManager._load_config()
        return config.get("mic_index", None)

    @staticmethod
    def save_admin_password(password):
        config = ConfigManager._load_config()
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
        config["admin_password"] = hashed
        ConfigManager._save_config(config)

    @staticmethod
    def load_admin_password():
        config = ConfigManager._load_config()
        return config.get("admin_password", "")

    @staticmethod
    def verify_admin_password(password):
        config = ConfigManager._load_config()
        stored = config.get("admin_password", "")
        if not stored:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except:
            return password == stored

    @staticmethod
    def has_admin_password():
        config = ConfigManager._load_config()
        return bool(config.get("admin_password"))

    @staticmethod
    def save_api_key(api_key):
        config = ConfigManager._load_config()
        config["uskopazar_api_key"] = api_key
        ConfigManager._save_config(config)

    @staticmethod
    def load_api_key():
        config = ConfigManager._load_config()
        if config.get("uskopazar_api_key_encrypted"):
            return CryptoManager.decrypt(config.get("uskopazar_api_key", ""))
        return config.get("uskopazar_api_key", "")

    @staticmethod
    def delete_api_key():
        config = ConfigManager._load_config()
        if "uskopazar_api_key" in config:
            del config["uskopazar_api_key"]
            ConfigManager._save_config(config)

    @staticmethod
    def save_default_server(server):
        config = ConfigManager._load_config()
        config["default_server"] = server
        ConfigManager._save_config(config)

    @staticmethod
    def load_default_server():
        config = ConfigManager._load_config()
        return config.get("default_server", "Tüm Zero")

    @staticmethod
    def save_ports(web_port, portfolio_port):
        config = ConfigManager._load_config()
        config["web_port"] = int(web_port)
        config["portfolio_port"] = int(portfolio_port)
        ConfigManager._save_config(config)

    @staticmethod
    def load_ports():
        config = ConfigManager._load_config()
        return config.get("web_port", 8765), config.get("portfolio_port", 9000)

    @staticmethod
    def save_encrypted(key, value):
        """Degeri sifreleyerek kaydet"""
        config = ConfigManager._load_config()
        config[key] = CryptoManager.encrypt(value)
        config[f"{key}_encrypted"] = True
        ConfigManager._save_config(config)

    @staticmethod
    def load_encrypted(key):
        """Sifrelenen degeri cozer"""
        config = ConfigManager._load_config()
        if config.get(f"{key}_encrypted"):
            return CryptoManager.decrypt(config.get(key, ""))
        return config.get(key, "")

    @staticmethod
    def save_sync_token(token):
        config = ConfigManager._load_config()
        config["pythonanywhere_token"] = token
        ConfigManager._save_config(config)

    @staticmethod
    def load_sync_token():
        config = ConfigManager._load_config()
        return config.get("pythonanywhere_token", "")

    @staticmethod
    def _load_config():
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}

    @staticmethod
    def _save_config(config):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except IOError as e:
            print(f"Config kaydedilemedi: {e}")
