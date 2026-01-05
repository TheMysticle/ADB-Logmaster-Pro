#!/bin/bash
APP_FILE="adb_logger.py"

if ! command -v adb &> /dev/null; then
    sudo apt update && sudo apt install -y android-tools-adb
fi

if ! command -v scrcpy &> /dev/null; then
    sudo snap install scrcpy
fi

if ! python3 -c "import customtkinter" &> /dev/null; then
    pip3 install customtkinter
fi

echo "Launching ADB Logmaster Pro..."
python3 "$APP_FILE"