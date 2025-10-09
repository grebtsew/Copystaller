# --- Basimage ---
    FROM ubuntu:24.04

    # --- Installera Python och pip ---
    RUN apt-get update && \
        apt-get install -y python3 python3-pip python3-venv build-essential git && \
        apt-get clean && rm -rf /var/lib/apt/lists/*
    
    # --- Installera PyInstaller ---
    RUN pip3 install --no-cache-dir pyinstaller  --break-system-packages

    COPY ./requirements.txt /requirements.txt
    RUN pip3 install -r /requirements.txt --break-system-packages

    
    # --- Set working directory ---
    WORKDIR /app
    
    # --- Kopiera skriptet ---
    COPY . .
    
    # --- Kör PyInstaller build som standard ---
    ENTRYPOINT ["pyinstaller", "--onefile", "./src/main.py"]
    