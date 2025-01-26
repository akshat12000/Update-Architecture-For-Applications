import requests
import tkinter as tk
from tkinter import messagebox
import os
import json
import hashlib
import sys

# Add the root directory (project directory) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.binarydiffs.akdelta import apply_optimized_delta_patch

# File paths
REPO_PATH = os.path.dirname(__file__) + "/repo" 
TEXT_FILE = os.path.dirname(__file__) + "/repo/A.txt"
VERSION_FILE = os.path.dirname(__file__) + "/version.json"
PATCH_FOLDER = os.path.dirname(__file__) + "/patches"

SERVER_URL = "http://127.0.0.1:5000"

def calculate_file_hash(file_path):
    """Calculate the hash of a file."""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def load_version(version_file):
    """Load version information from a JSON file."""
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            return json.load(f)
    return {"version": "0.0.0"}

def save_version(version_file, version_data):
    """Save version information to a JSON file."""
    with open(version_file, "w") as f:
        json.dump(version_data, f, indent=4)

def apply_patch(file_path, patch_content):
    """
    Apply a unified diff patch to a base file.
    """
    apply_optimized_delta_patch(file_path, patch_content)

def request_file_from_server(file_name):
    """Request the file from the server."""
    response = requests.post(f"{SERVER_URL}/get_file", json={"file_name": file_name})
    if response.status_code == 200:
        return response.json()
    else:
        messagebox.showerror("Error", f"Failed to request file: {response.json().get('error', 'Unknown error')}")
        return None

class UpdateClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Client Update Tool")

        self.version_data = load_version(VERSION_FILE)
        self.patch_files = []
        self.updated_files = []
        self.corrupted_files = []

        # UI Components
        self.check_button = tk.Button(master, text="Check for Updates", command=self.check_update)
        self.check_button.pack(pady=5)

        self.download_button = tk.Button(master, text="Download Patch", state=tk.DISABLED, command=self.download_patch)
        self.download_button.pack(pady=5)

        self.apply_button = tk.Button(master, text="Apply Patch", state=tk.DISABLED, command=self.apply_patch)
        self.apply_button.pack(pady=5)

        self.corruption_check_button = tk.Button(master, text="Check Corruption", command=self.check_corruption_action)
        self.corruption_check_button.pack(pady=5)

        self.corruption_fix_button = tk.Button(master, text="Fix Corruption", command=self.fix_corruption_action)
        self.corruption_fix_button.pack(pady=5)

        self.exit_button = tk.Button(master, text="Exit", command=master.quit)
        self.exit_button.pack(pady=10)

    def check_file_corruption(self, file_path, version_data):
        """Check if the file hash matches the hash in the version.json."""
        if not os.path.exists(file_path):
            messagebox.showinfo("Check Corruption", f"File '{file_path}' does not exist locally.")
            return True

        file_hash = calculate_file_hash(file_path)
        if file_hash != version_data["hash"]:
            messagebox.showerror("Corruption Detected", f"File '{file_path}' is corrupted! Hash mismatch.")
            data = {"file_name": version_data["file_name"], "version": version_data["version"], "hash": file_hash}
            self.corrupted_files.append(data)
            return True
        else:
            messagebox.showinfo("No Corruption", f"File '{file_path}' is intact. Hash matches.")
        return False

    def handle_file_corruption(self, file, version_file):
        """Handle file corruption by requesting the file from the server."""
        file_name = file["file_name"]
        file_path = os.path.join(REPO_PATH, file_name)
        response = request_file_from_server(file_name)
        if response:
            # Save the file content
            with open(file_path, 'w') as f:
                f.write(response["file_content"])

            # Update the version.json with the correct hash
            file["hash"] = response["hash"]
            file["version"] = response["version"]
            save_version(version_file, self.version_data)

            messagebox.showinfo("File Restored", f"File '{file_name}' restored successfully.")
        else:
            messagebox.showerror("Error", "Failed to restore the file.")

    def check_update(self):
        """Check for updates from the server."""

        # Check for new files from the server
        fGotNew = self.fetch_for_new_files_from_server()

        # Do this for every file in the version.json
        for file in self.version_data:
            file_version = file["version"]
            file_name = file["file_name"]
            response = requests.get(f"{SERVER_URL}/check_update/{file_name}", params={"version": file_version})
            update_info = response.json()

            if update_info["update"]:
                data = {
                    "file_name":  file_name,
                    "version": update_info["version"],
                    "hash": update_info["hash"],
                    "patch_url": update_info["patch_url"]
                }
                self.updated_files.append(data)

        if not self.updated_files and not fGotNew:
            messagebox.showinfo("Up-to-Date", "You already have the latest version.")
        else:
            messagebox.showinfo("Update Available", f"New version is available.")
            self.download_button.config(state=tk.NORMAL)

    def download_patch(self):
        """Download the patch from the server."""
        fSuccess = True

        for file in self.updated_files:
            patch_url = f"{SERVER_URL}{file['patch_url']}"
            patch_response = requests.get(patch_url)

            if patch_response.status_code == 200:
                patch_content = patch_response.content
                # Save the patch to a file
                with open(f"{PATCH_FOLDER}/{file["file_name"]}_{file['version']}.patch", "wb") as f:
                    f.write(patch_content)
                
                data = {
                    "file_name": file["file_name"],
                    "patch_file": f"{PATCH_FOLDER}/{file["file_name"]}_{file['version']}.patch",
                    "version": file["version"]
                }
                self.patch_files.append(data)

            else:
                fSuccess = False
            
        if fSuccess:
                self.updated_files = []
                messagebox.showinfo("Patch Downloaded", "Patch downloaded successfully. You can now apply it.")
                self.apply_button.config(state=tk.NORMAL)
        else:
            messagebox.showerror("Error", "Failed to download the patch(es).")

    def apply_patch(self):
        """Apply the downloaded patch to the local file."""
        
        fApplied = True
        # Apply patch for each file
        for patch_file in self.patch_files:
            try:
                file_path = os.path.join(REPO_PATH, patch_file["file_name"])
                apply_patch(file_path, patch_file["patch_file"])

                for file in self.version_data:
                    print(file["file_name"], patch_file["file_name"])

                    if file["file_name"] == patch_file["file_name"]:

                        # Update the version number
                        file["version"] = patch_file["version"]

                        # Update the hash of the file
                        file_hash = calculate_file_hash(file_path)
                        file["hash"] = file_hash
                        
                        save_version(VERSION_FILE, self.version_data)
                        break

            except Exception as e:
                fApplied = False

        if fApplied and self.patch_files:
            self.patch_files = []
            messagebox.showinfo("Update Applied", "Patch(es) applied successfully, and version updated.")
            self.download_button.config(state=tk.DISABLED)
            self.apply_button.config(state=tk.DISABLED)
        else:
            messagebox.showerror("Error", "Failed to apply the patch.")

    def fetch_for_new_files_from_server(self):
        """Fetch the list of files present on the server."""
        response = requests.get(f"{SERVER_URL}/sync_json_file")
        fGotNew = False

        if response.status_code == 200:
            server_json = response.json().get("file_content", [])
            # print(server_json)
            # now read this json and check if the file is present locally
            server_json = json.loads(server_json)

            for file in server_json:
                file_name = file["file_name"]
                file_path = os.path.join(REPO_PATH, file_name)
                if not os.path.exists(file_path):
                    data = request_file_from_server(file_name)
                    if data:
                        fGotNew = True
                        with open(file_path, 'w') as f:
                            f.write(data["file_content"])
                        self.version_data.append({"file_name": file_name, "version": data["version"], "hash": data["hash"]})
        else:
            messagebox.showerror("Error", f"Failed to fetch files: {response.json().get('error', 'Unknown error')}")

        if fGotNew:
            save_version(VERSION_FILE, self.version_data)
            messagebox.showinfo("Files Synced", "New files fetched from the server.")

    def check_corruption_action(self):
        """Check for corruption and display the result."""
        # check for all the files in the version.json
        for file in self.version_data:
            file_name = file["file_name"]
            file_path = os.path.join(REPO_PATH, file_name)
            self.check_file_corruption(file_path, file)

    def fix_corruption_action(self):
        """Fix corruption by requesting the file from the server."""
        # Fix corruption for all the corrupted files
        if not self.corrupted_files:
            messagebox.showinfo("No Corruption", "No corrupted files found.")
        else:
            for file in self.corrupted_files:
                self.handle_file_corruption(file, VERSION_FILE)
            self.corrupted_files = []

# Run the GUI
if __name__ == "__main__":

    root = tk.Tk()
    app = UpdateClient(root)
    root.mainloop()
