# ADB Logmaster Pro

A powerful, Python-based graphical interface for Android debugging, system logging, and root-level file management. Built with `CustomTkinter` for a sleek, modern dark-themed experience.

## Features

- **Real-time Logging**: Toggle between `Logcat` and `Dmesg` with live filtering and color-coded priority levels.
- **Root File Explorer**: A full-featured file manager with root (`su`) support. Navigate the system partition, create files/folders, delete items, and modify permissions (`chmod`).
- **Sensor Analyzer**: Deep-dive into device hardware sensors, viewing real-time status, vendor data, and power consumption.
- **System Stats & Dumps**: Quickly dump `batterystats`, `meminfo`, `procstats`, and `alarm` data.
- **Power Controls**: Shortcut buttons for Reboot, Recovery, Bootloader, and FastbootD.
- **Screen Mirroring**: Integrated support for scrcpy.

## Prerequisites

1.  **Python 3.x**
2.  **ADB (Android Debug Bridge)**: Must be installed and available in your system's PATH.
3.  **Required Libraries**:
    ```bash
    pip install customtkinter
    ```

## Installation

1. Clone this repository or download `adb_logger.py`.
2. Ensure your Android device has **USB Debugging** enabled.
3. For Root features, your device must be rooted and have a `su` binary installed.

## Scrcpy Integration

The "Launch Screen" functionality requires the `scrcpy` binaries to be present in the project directory.

1. Create a folder named `scrcpy` in the same directory as `adb_logger.py`.
2. Clone or download the [scrcpy](https://github.com/Genymobile/scrcpy) repository/binaries.
3. Place the `scrcpy` executable and `scrcpy-server` file inside that folder.

Project structure should look like this:
```text
.
├── adb_logger.py
└── scrcpy/
    ├── scrcpy
    └── scrcpy-server
```

*Note: If scrcpy is already installed globally in your system PATH, the app will attempt to use the global version as a fallback.*

## Usage

Run the application using:
```bash
python adb_logger.py
```

1. **Select Device**: Choose your connected device from the dropdown menu.
2. **Start Logging**: Click "Start Logging" to begin receiving Logcat or Dmesg output.
3. **Root Explorer**: Click "Root File Explorer" under Advanced Tools. Ensure "Use Root (su)" is checked in the sidebar to access protected partitions like `/data`.
4. **Permissions**: Use the "Properties" button in the File Explorer to change octal permissions (e.g., `755` or `644`) on selected files.

## Disclaimer

This tool performs root-level operations. Use caution when deleting or modifying system files, as improper use can lead to device instability or boot loops.