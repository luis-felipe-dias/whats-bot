import subprocess
import sys
import os

def main():
    print("🚀 Iniciando YUP Customer Service Platform...")
    
    if not os.path.exists("app/main.py"):
        print("❌ Execute este script na pasta raiz do projeto!")
        sys.exit(1)
    
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8001"]
    
    print(f"✅ Executando: {' '.join(cmd)}")
    subprocess.run(cmd)

if __name__ == "__main__":
    main()
