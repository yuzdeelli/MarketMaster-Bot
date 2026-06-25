import os
import string
import hashlib


class SecurityManager:
    def __init__(self):
        self.key_filename = "master.key"
        self.identity_filename = "identity.enc"
        self.checksum_filename = "checksum.txt"
        self.usb_path = self._find_usb()
        self.cipher = None

    def _find_usb(self):
        drives = [
            f"{d}:\\"
            for d in string.ascii_uppercase
            if os.path.exists(f"{d}:\\")
        ]
        for drive in drives:
            if os.path.exists(os.path.join(drive, self.key_filename)):
                return drive
        return None

    def verify_file_integrity(self):
        try:
            ident_path = os.path.join(self.usb_path, self.identity_filename)
            checksum_path = os.path.join(self.usb_path, self.checksum_filename)

            if not os.path.exists(checksum_path) or not os.path.exists(ident_path):
                return False

            with open(ident_path, "rb") as f:
                current_content = f.read()
                current_hash = hashlib.sha256(current_content).hexdigest()

            with open(checksum_path, "r") as f:
                stored_hash = f.read().strip()

            return current_hash == stored_hash
        except Exception:
            return False

    def initialize_cipher(self):
        from cryptography.fernet import Fernet
        self.usb_path = self._find_usb()
        if self.usb_path:
            try:
                key_path = os.path.join(self.usb_path, self.key_filename)
                with open(key_path, "rb") as kf:
                    self.cipher = Fernet(kf.read())
                return True
            except Exception:
                return False
        return False

    def verify_login(self, input_user, input_pass):
        if not self.usb_path or not self.cipher:
            return False, "USB Anahtar bulunamadi!"

        if not self.verify_file_integrity():
            return False, "GUVENLIK IHLAli: Dosya imzasi uyusmuyor!"

        try:
            ident_path = os.path.join(self.usb_path, self.identity_filename)
            with open(ident_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_text = self.cipher.decrypt(encrypted_data).decode()
            stored_user, stored_pass_hash = decrypted_text.split(":")
            input_pass_hash = hashlib.sha256(input_pass.encode()).hexdigest()

            if input_user == stored_user and input_pass_hash == stored_pass_hash:
                return True, "Onaylandi"
            return False, "Hatali bilgiler!"
        except Exception:
            return False, "Sifreleme anahtari gecersiz veya dosya bozuk!"
