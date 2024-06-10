import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox
from tkinter.ttk import Progressbar
from tqdm import tqdm
import logging
import zipfile

# Configure logging
logging.basicConfig(filename='minecraft_launcher.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL for fetching Minecraft versions
VERSIONS_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

# Fetch Minecraft versions
def fetch_versions():
    try:
        response = requests.get(VERSIONS_URL)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Minecraft versions: {e}")
        messagebox.showerror("Error", "Failed to fetch Minecraft versions. Please check your internet connection.")
        return None

# Download a file with progress
def download_file(url, path, progress_label, progress_bar, file_name):
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        # Ensure directory structure exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'wb') as file, tqdm(
            desc=file_name,
            total=total_size,
            unit='B',
            unit_scale=True,
            unit_divisor=1024,
        ) as bar:
            for data in response.iter_content(chunk_size=8192):
                file.write(data)
                bar.update(len(data))
                if total_size >= 1024 * 1024:
                    progress_label.config(text=f"Downloading {file_name}: {bar.n / (1024 * 1024):.2f} / {bar.total / (1024 * 1024):.2f} MB")
                else:
                    progress_label.config(text=f"Downloading {file_name}: {bar.n / 1024:.2f} / {bar.total / 1024:.2f} KB")
                root.update()  # Update the tkinter window
                progress_bar['value'] = (bar.n / total_size) * 100  # Update progress bar value

        # Check if the file extension is .zip and rename it to .jar if necessary
        if path.endswith('.zip'):
            new_path = path[:-4] + '.jar'
            os.rename(path, new_path)
            return new_path
        return path
    except Exception as e:
        logging.error(f"Failed to download file from {url}: {e}")
        messagebox.showerror("Error", f"Failed to download {file_name}: {e}")
        return None

# Download a Minecraft version
def download_version(version_id, progress_label, progress_bar):
    versions_data = fetch_versions()
    if versions_data:
        for version in versions_data['versions']:
            if version['id'] == version_id:
                try:
                    version_url = version['url']
                    version_details = requests.get(version_url).json()

                    appdata_path = os.path.expandvars("%APPDATA%")
                    version_dir = os.path.join(appdata_path, ".minecraft", "versions", version_id)
                    if not os.path.exists(version_dir):
                        os.makedirs(version_dir)

                    jar_url = version_details['downloads']['client']['url']
                    jar_path = os.path.join(version_dir, f"{version_id}.jar")
                    download_file(jar_url, jar_path, progress_label, progress_bar, f"{version_id}.jar")

                    json_path = os.path.join(version_dir, f"{version_id}.json")
                    download_file(version_url, json_path, progress_label, progress_bar, f"{version_id}.json")

                    with open(json_path, 'r') as f:
                        version_details = json.load(f)

                    libraries = version_details['libraries']
                    libraries_path = os.path.join(appdata_path, ".minecraft", "libraries")
                    natives_path = os.path.join(version_dir, "natives")

                    classpath_entries = [jar_path]
                    for library in libraries:
                        if 'downloads' in library and 'artifact' in library['downloads']:
                            artifact = library['downloads']['artifact']
                            artifact_path = os.path.join(libraries_path, *artifact['path'].split('/'))
                            download_file(artifact['url'], artifact_path, progress_label, progress_bar, artifact['path'].split('/')[-1])
                            classpath_entries.append(artifact_path)
                        if 'natives' in library['downloads']:
                            natives = library['downloads']['natives']
                            if 'windows' in natives:
                                native = natives['windows']
                                native_path = os.path.join(libraries_path, *native['path'].split('/'))
                                download_file(native['url'], native_path, progress_label, progress_bar, native['path'].split('/')[-1])
                                if not os.path.exists(natives_path):
                                    os.makedirs(natives_path)
                                with zipfile.ZipFile(native_path, 'r') as zip_ref:
                                    zip_ref.extractall(natives_path)

                    # Save classpath entries to a file
                    classpath_file = os.path.join(version_dir, "classpath.txt")
                    with open(classpath_file, 'w') as f:
                        f.write(';'.join(classpath_entries))

                    return version_details
                except Exception as e:
                    logging.error(f"Failed to download Minecraft version {version_id}: {e}")
                    messagebox.showerror("Error", f"Failed to download Minecraft version {version_id}: {e}")
    return None

# Launch Minecraft
def launch_minecraft():
    selected_version = version_listbox.get(tk.ACTIVE)
    if not selected_version:
        messagebox.showerror("Error", "Please select a Minecraft version.")
        return
    
    progress_label.config(text="")  # Reset progress label
    progress_bar['value'] = 0  # Reset progress bar value
    version_details = download_version(selected_version, progress_label, progress_bar)
    if not version_details:
        messagebox.showerror("Error", f"Failed to download Minecraft version {selected_version}.")
        return
    
    mc_directory = os.path.join(os.environ["APPDATA"], ".minecraft")
    mc_jar = os.path.join(mc_directory, "versions", selected_version, f"{selected_version}.jar")
    
    if not os.path.exists(mc_jar):
        messagebox.showerror("Error", f"Minecraft version {selected_version} not found.")
        return
    
    version_dir = os.path.join(mc_directory, "versions", selected_version)
    classpath_file = os.path.join(version_dir, "classpath.txt")
    natives_path = os.path.join(version_dir, "natives")
    
    main_class = "net.minecraft.client.main.Main"  # Main class for Minecraft

    # Placeholder values for required arguments
    access_token = "token"
    username = "username"
    uuid = "uuid"

    command = [
        'java', f'-Djava.library.path={natives_path}', '-cp', f'@{classpath_file}', main_class,
        '--accessToken', access_token,
        '--version', selected_version,
        '--username', username,
        '--uuid', uuid
    ]
    
    try:
        subprocess.run(command)
    except Exception as e:
        logging.error(f"Failed to launch Minecraft: {e}")
        messagebox.showerror("Error", f"Failed to launch Minecraft: {e}")

# Create the main window
root = tk.Tk()
root.title("Minecraft Launcher")
root.geometry("640x480")  # Set window size

# Version listbox
version_listbox = tk.Listbox(root)
version_listbox.pack(pady=20, expand=200)

# Fetch and display versions
if fetch_versions():
    display_versions()

# Launch button
launch_button = tk.Button(root, text="Launch Minecraft", command=launch_minecraft)
launch_button.pack(pady=20)

# Progress label
progress_label = tk.Label(root, text="")
progress_label.pack(side=tk.BOTTOM, pady=(0, 20))  # Position at the bottom with 5px padding above

# Progress bar
progress_bar = Progressbar(root, orient=tk.HORIZONTAL, length=400, mode='determinate')  # Set width to 400px
progress_bar.pack(side=tk.BOTTOM, pady=20)  # Position at the bottom with 20px padding above

# Start the Tkinter event loop
root.mainloop()

# Log end of script execution
logging.info("Minecraft Launcher exited")
