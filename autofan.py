#!/usr/bin/env python3

import argparse
import time as t
from pynvml import *
import os
import sys
import shutil
import re
import subprocess
import memtemp

# Try to import sdnotify for systemd notifications, otherwise silently skip
try:
    from sdnotify import SystemdNotifier
except ImportError:
    SystemdNotifier = None

# --- Functions for colored text display ---
def get_color_text(color, text, bold=False):
    color_dict = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'cyan': '\033[96m',
        'blue': '\033[94m',
        'white': '\033[97m',
        'reset': '\033[0m'
    }
    bold_seq = '\033[1m' if bold else ''
    return f'{bold_seq}{color_dict[color]}{text}{color_dict["reset"]}'

# To calculate the visible length of a string (by removing ANSI escape codes)
ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
def visible_length(text):
    return len(ansi_escape.sub('', text))

def pad_text(text, width):
    """Pads the string with spaces to reach a visible width of 'width'."""
    return text + ' ' * (width - visible_length(text))

# --- Fonctions d'affichage en colonnes ---
def print_columns(blocks, padding=4):
    """
    Assemble a list of blocks (each being a list of lines)
    into columns, based on the terminal width.
    Returns a list of final output lines.
    """
    if not blocks:
        return []

    # Calculate the maximum visible width of each block
    col_width = max(visible_length(line) for block in blocks for line in block)

    term_width = shutil.get_terminal_size((80, 20)).columns
    # Number of columns that can fit in the terminal
    cols = max(1, term_width // (col_width + padding))

    # Group the blocks into rows (each row contains up to 'cols' blocks)
    rows_of_blocks = [blocks[i:i+cols] for i in range(0, len(blocks), cols)]
    output_lines = []
    for row in rows_of_blocks:
        # Calculate the maximum height of the row (number of lines in the tallest block)
        max_lines = max(len(block) for block in row)
        # Pad blocks that have fewer lines
        for block in row:
            if len(block) < max_lines:
                block.extend([""] * (max_lines - len(block)))
        # Assemble each line of the row by adding a fixed spacing
        for i in range(max_lines):
            line_parts = [pad_text(block[i], col_width) for block in row]
            output_lines.append((" " * padding).join(line_parts))
    return output_lines

def get_separator(char='=', length=40):
    return char * length

def move_cursor_up(lines=1):
    print(f'\033[{lines}F', end='')

def clear_terminal():
    os.system('cls' if os.name == 'nt' else 'clear')

def display_icon(value, threshold, icon="⚠️"):
    """Returns an icon if the value exceeds a threshold."""
    return icon if value >= threshold else "✅"

# --- Fonctions de contrôle manuel des ventilateurs via nvidia-settings ---
def set_fan_speed(gpu_index, speed):
    """
    Sets the fan speed (in %) for the specified GPU.
    Uses nvidia-settings to force manual control.
    """
    try:
        # Enable manual fan control
        subprocess.run(["nvidia-settings", "-a", f"[gpu:{gpu_index}]/GPUFanControlState=1"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Set the target fan speed
        subprocess.run(["nvidia-settings", "-a", f"[fan:{gpu_index}]/GPUTargetFanSpeed={int(speed)}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        # On error, do nothing
        pass

def revert_fan_control(gpu_index):
    """
    Reverts the fan control to automatic for the specified GPU.
    """
    try:
        subprocess.run(["nvidia-settings", "-a", f"[gpu:{gpu_index}]/GPUFanControlState=0"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        pass

def parse_args():
    nvmlInit()
    default_devices = list(range(nvmlDeviceGetCount()))
    parser = argparse.ArgumentParser(description='Monitor Nvidia GPUs.')
    parser.add_argument('--interval', type=int, default=1, help='Sampling interval in seconds (default: 1)')
    parser.add_argument('--memtemp', action='store_true', help='Also display GDDR6 memory temperatures (requires root)')
    # Nouveaux arguments pour les paramètres de contrôle des ventilateurs
    parser.add_argument('--fan-temp-threshold', type=float, default=60.0,
                        help='Temperature threshold to start increasing fan speed (°C) (default: 60)')
    parser.add_argument('--fan-temp-max', type=float, default=80.0,
                        help='Temperature at which fan is forced to 100%% (°C) (default: 80)')
    args = parser.parse_args()
    return args, default_devices

def read_memtemp():
    if os.geteuid() == 0:
        try:
            return memtemp.get_mem_temps()
        except Exception as e:
            print(f"Failed to get GDDR6 temperatures: {e}")            
    return []

def main():
    args, default_devices = parse_args()
    total_lines = 0  # For refreshing the display

    # If GDDR6 temperature display is requested, check for root privileges
    if args.memtemp and os.geteuid() != 0:
        print("Vous devez lancer en root pour afficher les températures GDDR6 et contrôler les ventilateurs.")
        t.sleep(3)

    # Initialize sdnotify if available
    notifier = None
    if SystemdNotifier is not None:
        notifier = SystemdNotifier()
        notifier.notify("READY=1")

    #clear_terminal()

    while True:
        mem_temps = read_memtemp()

        # Clear the terminal
        #if int(t.time()) % 10 == 0:
        clear_terminal()

        total_power = 0
        total_vram_used = 0
        total_utilization_gpu = 0

        gpu_blocks = []  # List of information blocks for each GPU

        for device_id in default_devices:
            handle = nvmlDeviceGetHandleByIndex(device_id)
            power = nvmlDeviceGetPowerUsage(handle) / 1000.0
            gpu_temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
            memory_info = nvmlDeviceGetMemoryInfo(handle)
            utilization = nvmlDeviceGetUtilizationRates(handle)
            gpu_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
            mem_clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_MEM)
            max_tdp = nvmlDeviceGetPowerManagementLimit(handle) / 1000.0
            gpu_name = nvmlDeviceGetName(handle)
            try:
                # Retrieve the fan speed (in %)
                fan_speed_nvml = nvmlDeviceGetFanSpeed(handle)
            except NVMLError_NotSupported:
                fan_speed_nvml = 'Not Supported'

            total_power += power
            total_vram_used += memory_info.used
            total_utilization_gpu += utilization.gpu

            # Retrieve overclocking parameters
            try:
                core_lock = nvmlDeviceGetApplicationsClock(handle, NVML_CLOCK_GRAPHICS)
                if core_lock == 0:
                    core_lock = gpu_clock
            except NVMLError:
                core_lock = gpu_clock
            core_offset = core_lock - gpu_clock

            try:
                mem_lock = nvmlDeviceGetApplicationsClock(handle, NVML_CLOCK_MEM)
                if mem_lock == 0:
                    mem_lock = mem_clock
            except NVMLError:
                mem_lock = mem_clock
            mem_offset = mem_lock - mem_clock

            # Manual fan control based on GDDR6 temperature
            # (only if --memtemp is enabled and a temperature is available)
            if args.memtemp and (device_id < len(mem_temps)) and (mem_temps[device_id] is not None):
                gddr6_temp = mem_temps[device_id]
                if gddr6_temp >= args.fan_temp_threshold:
                    # Linear interpolation: from fan_temp_threshold to fan_temp_max
                    new_fan_speed = ((gddr6_temp - args.fan_temp_threshold) /
                                     (args.fan_temp_max - args.fan_temp_threshold)) * 100
                    new_fan_speed = min(100, new_fan_speed)
                    set_fan_speed(device_id, new_fan_speed)
                    fan_control_info = get_color_text('green', f"Manual Fan Speed: {int(new_fan_speed)}%")
                else:
                    revert_fan_control(device_id)
                    fan_control_info = get_color_text('green', "Fan Control: Auto")
            else:
                fan_control_info = get_color_text('green', f"Fan Speed: {fan_speed_nvml}%")

            # Build the information block for the current GPU
            block = []
            block.append(get_color_text('cyan', f'GPU {device_id} ({gpu_name}) Status:', bold=True))
            block.append(get_color_text('green', f'Power: {power:.2f} W / Max TDP: {max_tdp:.2f} W'))
            block.append(get_color_text('yellow', f'Temp: {gpu_temp} °C {display_icon(gpu_temp, 80, "🔥")}'))
            # Display GDDR6 temperature if enabled
            if args.memtemp:
                if device_id < len(mem_temps) and mem_temps[device_id] is not None:
                    block.append(get_color_text('yellow', f'GDDR6: {mem_temps[device_id]} °C {display_icon(mem_temps[device_id], 100, "🔥")}'))
                else:
                    block.append(get_color_text('yellow', 'GDDR6 Temp: Not Available'))
            block.append(get_color_text('green', f'Utilization - GPU: {utilization.gpu}%, Memory: {utilization.memory}%'))
            block.append(get_color_text('yellow', f'Clocks - GPU: {gpu_clock} MHz, Memory: {mem_clock} MHz'))
            block.append(get_color_text('green', f'Memory - Total: {memory_info.total/(1024**2):.2f} MB, Used: {memory_info.used/(1024**2):.2f} MB'))
            block.append(fan_control_info)
            block.append(get_color_text('green', 'OC Parameters:'))
            block.append(get_color_text('green', f'  Core clock offset: {core_offset} MHz'))
            block.append(get_color_text('green', f'  Core clock lock: {core_lock} MHz'))
            block.append(get_color_text('green', f'  Memory clock offset: {mem_offset} MHz'))
            block.append(get_color_text('green', f'  Memory clock lock: {mem_lock} MHz'))
            block.append(get_color_text('green', f'  Powerlimit: {max_tdp:.2f} W'))

            gpu_blocks.append(block)

        # Prepare header and footer for display
        header_lines = [
            get_separator('=', 40),
            get_color_text('blue', 'NVIDIA GPU Monitoring Tool', bold=True),
            get_separator('=', 40)
        ]
        grid_lines = print_columns(gpu_blocks, padding=4)
        avg_utilization_gpu = total_utilization_gpu / len(default_devices)
        footer_lines = [
            get_color_text('cyan', f'Total power consumption: {total_power:.2f} W', bold=True),
            get_color_text('cyan', f'Total VRAM used: {total_vram_used/(1024**2):.2f} MB', bold=True),
            get_color_text('yellow', f'Total GPU utilization: {total_utilization_gpu:.2f}%', bold=True),
            get_color_text('yellow', f'Average GPU utilization: {avg_utilization_gpu:.2f}%', bold=True)
        ]
        
        all_lines = header_lines + grid_lines + footer_lines

        # Clear the previous output by moving the cursor up
        if total_lines > 0:
            move_cursor_up(total_lines)
        for line in all_lines:
            print(line)
        total_lines = len(all_lines)
        
        # Send the WATCHDOG notification if sdnotify is available
        if notifier:
            notifier.notify("WATCHDOG=1")
            
        t.sleep(args.interval)

if __name__ == '__main__':
    main()
