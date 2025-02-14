NVIDIA AutoFan Monitoring Tool
==============================

A Python-based NVIDIA GPU monitoring and fan control tool for Linux. This tool displays real-time GPU metrics (temperature, power usage, utilization, clock speeds, etc.) and controls fan speeds via NVIDIA settings. It also supports GDDR6 memory temperature monitoring (requires root privileges) through direct memory mapping.


Based On
--------

This repository is based on the work from [gpuFire](https://github.com/Nondzu/gpuFire) by Nondzu.


Features
--------

*   **Real-time Monitoring:** Displays GPU power consumption, temperature, memory usage, utilization, and clock speeds.
*   **Fan Control:** Automatically or manually control fan speeds based on GPU and GDDR6 memory temperatures.
    *   `--fan-temp-threshold` (default: 70.0 °C): Temperature to start increasing fan speed.
    *   `--fan-temp-max` (default: 90.0 °C): Temperature at which fan speed is forced to 100%.
*   **Overclocking Parameters:** Displays overclocking details such as core/memory offsets and locked clock speeds.
*   **GDDR6 Temperature Monitoring:** (Requires root) Monitors GDDR6 memory temperatures using direct access to `/dev/mem`.
*   **Systemd Service with Watchdog Support:** Run the tool as a service on Ubuntu 24.04 with a built-in watchdog mechanism.

Requirements
------------

*   Python 3.x
*   [pynvml](https://pypi.org/project/pynvml/)
*   NVIDIA drivers and `nvidia-settings`
*   (Optional) [sdnotify](https://pypi.org/project/sdnotify/) for systemd watchdog notifications

_Note:_ GDDR6 memory temperature monitoring requires root privileges since it reads from `/dev/mem`.

Installation
------------

1.  **Clone the repository:**
    
        git clone https://github.com/Astral0/nvidia-autofan.git
        cd nvidia-autofan
    
2.  **Install Python dependencies:**
    
        pip3 install -r requirements.txt
    
    To enable systemd watchdog notifications, also install:
    
        pip3 install sdnotify
    
3.  **Install the project to your desired location (e.g., /opt/nvidia-autofan):**
    
        sudo cp -r . /opt/nvidia-autofan
    

Running as a Systemd Service
----------------------------

A sample systemd unit file is provided in the file `nvidia-autofan.service`. In this file, the `--interval` parameter is fixed to 60 seconds. You can also adjust the fan control parameters using the `--fan-temp-threshold` and `--fan-temp-max` arguments if needed.

1.  **Copy the service file to /etc/systemd/system:**
    
        sudo cp nvidia-autofan.service /etc/systemd/system/
    
2.  **Reload the systemd daemon:**
    
        sudo systemctl daemon-reload
    
3.  **Enable and start the service:**
    
        sudo systemctl enable nvidia-autofan.service
        sudo systemctl start nvidia-autofan.service
    
4.  **Check the service status:**
    
        sudo systemctl status nvidia-autofan.service
    

Running the Script Manually
---------------------------

You can also run the script directly in a terminal. This is useful for testing or if you prefer not to run it as a service. Here is an example command:

    python3 /opt/nvidia-autofan/autofan.py --memtemp --interval 60 --fan-temp-threshold 70.0 --fan-temp-max 90.0

If you run the script manually, it will output real-time GPU metrics and control the fan speeds accordingly. To stop the script, simply press `Ctrl+C` in the terminal.


Command-Line Arguments
----------------------

The following command-line arguments are available:

*   `--interval`: The sampling interval in seconds. This defines how often the tool updates the metrics.  
    _Default:_ 1 (Note: the systemd service sets this to 60 seconds.)
*   `--memtemp`: When specified, the tool will also display the GDDR6 memory temperatures.  
    _Note:_ Requires root privileges since it reads from `/dev/mem`.
*   `--fan-temp-threshold`: The temperature threshold (in °C) at which the fan speed begins to increase.  
    _Default:_ 70.0 °C
*   `--fan-temp-max`: The temperature (in °C) at which the fan speed is forced to 100%.  
    _Default:_ 90.0 °C


Contributing
------------

Contributions are welcome! Please feel free to open issues or submit pull requests with improvements and bug fixes.

License
-------

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
