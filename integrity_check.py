import os
import py_compile
import sys

def check_files():
    failed = []
    for root, dirs, files in os.walk('.'):
        if '.venv' in dirs:
            dirs.remove('.venv')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
        
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    py_compile.compile(path, doraise=True)
                except py_compile.PyCompileError:
                    failed.append(path)
                except Exception as e:
                    print(f"Error checking {path}: {e}")
                    failed.append(path)
    
    if failed:
        print("SYNTAX_CHECK_FAILED")
        for f in failed:
            print(f)
        sys.exit(1)
    else:
        print("SYNTAX_CHECK_PASSED")

if __name__ == "__main__":
    check_files()
