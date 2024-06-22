import configparser
import os

class UserModel:
    def __init__(self):
        self.ip = ""
        self.port = ""
        self.config_file_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.ensure_config_file()
        self.update_from_config()

    def ensure_config_file(self):
        if not os.path.exists(self.config_file_path):
            self.save_to_config('192.168.0.224', '5000')
            print(f"Config file created at {self.config_file_path} with default values.")

    def update_from_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file_path)
        
        self.ip = config.get('network', 'ip')
        self.port = config.get('network', 'port')

    def __str__(self):
        return f"UserModel(ip={self.ip}, port={self.port})"
    
    def save_to_config(self, ip, port):
        config = configparser.ConfigParser()
        config['network'] = {
            'ip': ip,
            'port': port
        }
        with open(self.config_file_path, 'w') as configfile:
            config.write(configfile)


# Example usage
if __name__ == "__main__":
    user_model = UserModel()
    print(user_model)