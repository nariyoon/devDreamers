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
            config = configparser.ConfigParser()
            config['network'] = {
                'ip': '192.168.0.224',
                'port': '5000'
            }
            with open(self.config_file_path, 'w') as configfile:
                config.write(configfile)
            print(f"Config file created at {self.config_file_path} with default values.")

    def update_from_config(self):
        config = configparser.ConfigParser()
        config.read(self.config_file_path)
        
        self.ip = config.get('network', 'ip')
        self.port = config.get('network', 'port')

    def __str__(self):
        return f"UserModel(ip={self.ip}, port={self.port})"

# Example usage
if __name__ == "__main__":
    user_model = UserModel()
    print(user_model)