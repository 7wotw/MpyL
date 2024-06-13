import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from tqdm import tqdm
import logging
import zipfile
import sys

# Configure logging
logging.basicConfig(filename='minecraft_launcher.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# URL for fetching Minecraft versions
VERSIONS_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

class MinecraftLauncher:
    def __init__(self, master):
        self.master = master
        master.title("Minecraft Launcher")
        master.resizable(False, False)  # Make the window unresizable

        # Version select dropdown
        self.version_var = tk.StringVar()
        self.version_label = ttk.Label(master, text="Version:")
        self.version_label.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="e")
        self.version_select = ttk.Combobox(master, textvariable=self.version_var, state="readonly", width=20)
        self.version_select.grid(row=0, column=1, padx=(5, 10), pady=10, sticky="w")

        # Launch button
        self.launch_button = ttk.Button(master, text="Launch", command=self.launch_minecraft)
        self.launch_button.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 40))

        # Progress label
        self.progress_label = ttk.Label(master, text="")
        self.progress_label.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="w")

        # Progress bar
        self.progress_bar = ttk.Progressbar(master, orient=tk.HORIZONTAL, length=400, mode='determinate')  # Set width to 400px
        self.progress_bar.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 10))

        # Settings button
        self.settings_button = ttk.Button(master, text="Settings")
        self.settings_button.grid(row=4, column=1, padx=10, pady=(0, 10), sticky="e")

        # Fetch and display versions
        self.display_versions()

    # Fetch Minecraft versions
    def fetch_versions(self):
        try:
            response = requests.get(VERSIONS_URL)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logging.error(f"Failed to fetch Minecraft versions: {e}")
            messagebox.showerror("Error", "Failed to fetch Minecraft versions. Please check your internet connection.")
            return None

    # Download a file with progress
    def download_file(self, url, path, file_name):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            if total_size == 0:
                logging.warning(f"Failed to get total file size for {file_name}.")
                total_size = None  # Set total size to None if not available

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
                    if total_size is not None:
                        bar.update(len(data))
                        self.progress_label.config(text=f"Downloading {file_name}: {bar.n / (1024 * 1024):.2f} / {bar.total / (1024 * 1024):.2f} MB")
                        self.master.update()  # Update the tkinter window
                        self.progress_bar['value'] = (bar.n / total_size) * 100  # Update progress bar value

            return path
        except Exception as e:
            logging.error(f"Failed to download file from {url}: {e}")
            messagebox.showerror("Error", f"Failed to download {file_name}: {e}")
            return None

    # Download LWJGL
    def download_lwjgl(self):
        lwjgl_zip_url = "https://altushost-swe.dl.sourceforge.net/project/java-game-lib/Official%20Releases/LWJGL%202.9.3/lwjgl-2.9.3.zip"
        lwjgl_zip_path = os.path.join(os.path.expanduser("~"), ".minecraft", "lwjgl-2.9.3.zip")
        lwjgl_path = os.path.join(os.path.expanduser("~"), ".minecraft", "lwjgl-2.9.3")

        if not os.path.exists(lwjgl_path):
            downloaded_file = self.download_file(lwjgl_zip_url, lwjgl_zip_path, "lwjgl-2.9.3.zip")
            if downloaded_file:
                try:
                    with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
                        zip_ref.extractall(os.path.dirname(lwjgl_path))  # Extract to parent directory to handle nested structure
                    logging.info(f"Extracted LWJGL to {lwjgl_path}")
                    print(f"Extracted LWJGL to {lwjgl_path}")  # Print the extracted path
                except Exception as e:
                    logging.error(f"Failed to extract LWJGL: {e}")
                    messagebox.showerror("Error", f"Failed to extract LWJGL: {e}")
                    return None
        else:
            logging.info(f"LWJGL already extracted at {lwjgl_path}")
            print(f"LWJGL already extracted at {lwjgl_path}")  # Print the existing path

        # Correct path for native libraries
        natives_dir = os.path.join(lwjgl_path, "lwjgl-2.9.3", "native", "windows")
        expected_files = ['lwjgl.dll', 'lwjgl64.dll']
        for file in expected_files:
            if not os.path.exists(os.path.join(natives_dir, file)):
                logging.error(f"Missing LWJGL native library: {file}")
                messagebox.showerror("Error", f"Missing LWJGL native library: {file}")
                return None

        return natives_dir  # Return the natives directory directly

    def download_version(self, version_id):
        versions_data = self.fetch_versions()
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
                        self.download_file(jar_url, jar_path, f"{version_id}.jar")

                        json_path = os.path.join(version_dir, f"{version_id}.json")
                        with open(json_path, 'w') as f:
                            json.dump(version_details, f)

                        libraries = version_details.get('libraries', [])
                        libraries_path = os.path.join(appdata_path, ".minecraft", "libraries")

                        classpath_entries = [jar_path]  # Add Minecraft JAR to classpath

                        for library in libraries:
                            if 'downloads' in library:
                                artifact = library['downloads'].get('artifact', {})
                                if 'path' in artifact and 'url' in artifact:
                                    artifact_path = os.path.join(libraries_path, *artifact['path'].split('/'))
                                    self.download_file(artifact['url'], artifact_path, artifact['path'].split('/')[-1])
                                    classpath_entries.append(artifact_path)

                        # Save classpath entries to a file
                        classpath_file = os.path.join(version_dir, "classpath.txt")
                        with open(classpath_file, 'w') as f:
                            f.write(';'.join(classpath_entries))

                        logging.info(f"Generated classpath for version {version_id}: {classpath_entries}")

                        return version_details
                    except Exception as e:
                        logging.error(f"Failed to download Minecraft version {version_id}: {e}")
                        messagebox.showerror("Error", f"Failed to download Minecraft version {version_id}: {e}")
        return None

    # Display Minecraft versions
    def display_versions(self):
        versions_data = self.fetch_versions()
        if versions_data:
            versions = versions_data['versions']
            version_ids = [version['id'] for version in versions]
            self.version_select['values'] = version_ids
            self.version_select.current(0)  # Select the first version by default

    # Launch Minecraft
    def launch_minecraft(self):
        selected_version = self.version_var.get()
        if not selected_version:
            messagebox.showerror("Error", "Please select a Minecraft version.")
            return

        self.progress_label.config(text="")  # Reset progress label
        self.progress_bar['value'] = 0  # Reset progress bar value
        version_details = self.download_version(selected_version)
        if not version_details:
            messagebox.showerror("Error", f"Failed to download Minecraft version {selected_version}.")
            return

        mc_directory = os.path.join(os.environ["APPDATA"], ".minecraft")
        mc_jar = os.path.join(mc_directory, "versions", selected_version, f"{selected_version}.jar")

        if not os.path.exists(mc_jar):
            messagebox.showerror("Error", f"Minecraft version {selected_version} not found.")
            return

        main_class = version_details['mainClass']  # Get main class from version details

        # Placeholder values for required arguments
        access_token = "token"
        username = "username"
        uuid = "uuid"

        # Set java.library.path to include LWJGL natives directory
        lwjgl_natives_dir = self.download_lwjgl()  # LWJGL natives directory
        if not lwjgl_natives_dir:
            return

        java_library_path = lwjgl_natives_dir  # Directly use natives_dir

        # Print the java.library.path for debugging
        print(f"java.library.path: {java_library_path}")
        logging.info(f"java.library.path: {java_library_path}")

        # Construct the classpath including Minecraft JAR and dependencies
        classpath = [mc_jar]
        libraries = version_details.get('libraries', [])
        for library in libraries:
            if 'downloads' in library:
                artifact = library['downloads'].get('artifact', {})
                if 'path' in artifact and 'url' in artifact:
                    artifact_path = os.path.join(mc_directory, "libraries", *artifact['path'].split('/'))
                    classpath.append(artifact_path)

        # Construct the command to launch Minecraft
        command = [
            'java', '-Djava.library.path=' + java_library_path, '-cp', os.pathsep.join(classpath), main_class,
            '--accessToken', access_token,
            '--version', selected_version,
            '--username', username,
            '--uuid', uuid
        ]

        # Log the command for debugging
        logging.info(f"Executing command: {' '.join(command)}")
        print(f"Executing command: {' '.join(command)}")

        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to launch Minecraft: {e}")
            messagebox.showerror("Error", f"Failed to launch Minecraft: {e}")
        except Exception as e:
            logging.error(f"Failed to launch Minecraft: {e}")
            messagebox.showerror("Error", f"Failed to launch Minecraft: {e}")

def main():
    root = tk.Tk()
    minecraft_launcher = MinecraftLauncher(root)
    root.mainloop()

if __name__ == "__main__":
    main()
