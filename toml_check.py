import tomllib
import os

def validate_toml():
    failed = []
    for root, dirs, files in os.walk('.'):
        if '.venv' in dirs:
            dirs.remove('.venv')
        for file in files:
            if file.endswith('.toml'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        tomllib.load(f)
                except Exception as e:
                    print(f"Invalid TOML {path}: {e}")
                    failed.append(path)
    
    if not failed:
        print("ALL_TOML_VALID")
    else:
        print("TOML_CHECK_FAILED")

if __name__ == "__main__":
    validate_toml()
