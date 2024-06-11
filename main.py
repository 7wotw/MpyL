import os
import json
import requests
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk
from tqdm import tqdm
import logging
import zipfile
import platform

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

    # Download LWJGL library based on platform
    def download_lwjgl(self, version_dir):
        lwjgl_url = None
        lwjgl_path = None
        os_name = platform.system().lower()

        if os_name == "windows":
            lwjgl_url = "https://libraries.minecraft.net/org/lwjgl/lwjgl/lwjgl-platform/2.9.4-nightly-20150209/lwjgl-platform-2.9.4-nightly-20150209-natives-windows.jar"
        elif os_name == "linux":
            lwjgl_url = "https://libraries.minecraft.net/org/lwjgl/lwjgl/lwjgl-platform/2.9.4-nightly-20150209/lwjgl-platform-2.9.4-nightly-20150209-natives-linux.jar"
        elif os_name == "darwin":
            lwjgl_url = "https://libraries.minecraft.net/org/lwjgl/lwjgl/lwjgl-platform/2.9.4-nightly-20150209/lwjgl-platform-2.9.4-nightly-20150209-natives-osx.jar"
        else:
            messagebox.showerror("Error", "Unsupported operating system.")
            return None

        lwjgl_path = os.path.join(version_dir, "natives", "lwjgl64")
        lwjgl_jar = os.path.join(version_dir, "natives", "lwjgl-platform.jar")

        # Download LWJGL
        if lwjgl_url:
            lwjgl_jar = self.download_file(lwjgl_url, lwjgl_jar, "lwjgl-platform.jar")

        return lwjgl_path

    # Download a Minecraft version
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
                        self.download_file(version_url, json_path, f"{version_id}.json")

                        with open(json_path, 'r') as f:
                            version_details = json.load(f)

                        libraries = version_details['libraries']
                        libraries_path = os.path.join(appdata_path, ".minecraft", "libraries")
                        natives_path = os.path.join(version_dir, "natives")

                        classpath_entries = [jar_path]
                        lwjgl_path = self.download_lwjgl(version_dir)

                        for library in libraries:
                            if 'downloads' in library and 'artifact' in library['downloads']:
                                artifact = library['downloads']['artifact']
                                artifact_path = os.path.join(libraries_path, *artifact['path'].split('/'))
                                self.download_file(artifact['url'], artifact_path, artifact['path'].split('/')[-1])
                                classpath_entries.append(artifact_path)

                        # Save classpath entries to a file
                        classpath_file = os.path.join(version_dir, "classpath.txt")
                        with open(classpath_file, 'w') as f:
                            f.write(';'.join(classpath_entries))

                        return version_details, lwjgl_path
                    except Exception as e:
                        logging.error(f"Failed to download Minecraft version {version_id}: {e}")
                        messagebox.showerror("Error", f"Failed to download Minecraft version {version_id}: {e}")
        return None, None

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
        version_details, lwjgl_path = self.download_version(selected_version)
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

        main_class = "net.minecraft.client.main.Main"  # Main class for Minecraft

        # Placeholder values for required arguments
        access_token = "token"
        username = "username"
        uuid = "uuid"

        command = [
            'java', '-Djava.library.path=' + lwjgl_path, '-cp', f'@{classpath_file}', main_class,
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

def main():
    root = tk.Tk()
    minecraft_launcher = MinecraftLauncher(root)
    root.mainloop()

if __name__ == "__main__":
    main()
