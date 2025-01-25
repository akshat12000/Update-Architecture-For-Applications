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

def check_file_corruption(file_path, version_file):
    """Check if the file hash matches the hash in the version.json."""
    version_data = load_version(version_file)
    if not os.path.exists(file_path):
        messagebox.showinfo("Check Corruption", f"File '{file_path}' does not exist locally.")
        return True

    file_hash = calculate_file_hash(file_path)
    if file_hash != version_data["hash"]:
        messagebox.showerror("Corruption Detected", f"File '{file_path}' is corrupted! Hash mismatch.")
        return True
    else:
        messagebox.showinfo("No Corruption", f"File '{file_path}' is intact. Hash matches.")
        return False

def request_file_from_server(file_name):
    """Request the file from the server."""
    response = requests.post(f"{SERVER_URL}/get_file", json={"file_name": file_name})
    if response.status_code == 200:
        return response.json()
    else:
        messagebox.showerror("Error", f"Failed to request file: {response.json().get('error', 'Unknown error')}")
        return None

def handle_file_corruption(file_path, version_file):
    """Handle file corruption by requesting the file from the server."""
    file_name = os.path.basename(file_path)
    response = request_file_from_server(file_name)
    if response:
        # Save the file content
        with open(file_path, 'w') as f:
            f.write(response["file_content"])

        # Update the version.json with the correct hash
        correct_hash = calculate_file_hash(file_path)
        version_data = {"version": response["version"], "hash": correct_hash}
        save_version(version_file, version_data)

        messagebox.showinfo("File Restored", f"File '{file_name}' restored successfully.")
    else:
        messagebox.showerror("Error", "Failed to restore the file.")

class UpdateClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Client Update Tool")

        self.version_data = load_version(VERSION_FILE)
        self.current_version = self.version_data["version"]
        self.current_hash = self.version_data.get("hash", "")

        # UI Components
        self.info_label = tk.Label(master, text=f"Current Version: {self.current_version}")
        self.info_label.pack(pady=10)

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

        self.update_info = None

    def check_update(self):
        """Check for updates from the server."""
        response = requests.get(f"{SERVER_URL}/check_update", params={"version": self.current_version})
        self.update_info = response.json()

        if self.update_info["update"]:
            messagebox.showinfo("Update Available", f"New version {self.update_info['version']} is available.")
            self.download_button.config(state=tk.NORMAL)
        else:
            messagebox.showinfo("Up-to-Date", "You already have the latest version.")

    def download_patch(self):
        """Download the patch from the server."""
        patch_url = f"{SERVER_URL}{self.update_info['patch_url']}"
        patch_response = requests.get(patch_url)

        if patch_response.status_code == 200:
            self.patch_content = patch_response.content
            # Save the patch to a file
            with open(f"{PATCH_FOLDER}/{self.update_info['version']}.patch", "wb") as f:
                f.write(self.patch_content)
            self.patch_file = f"{PATCH_FOLDER}/{self.update_info['version']}.patch"
            messagebox.showinfo("Patch Downloaded", "Patch downloaded successfully. You can now apply it.")
            self.apply_button.config(state=tk.NORMAL)
        else:
            messagebox.showerror("Error", "Failed to download the patch.")

    def apply_patch(self):
        """Apply the downloaded patch to the local file."""
        try:
            apply_patch(TEXT_FILE, self.patch_file)

            # Update the version number
            self.current_version = self.update_info["version"]
            self.version_data["version"] = self.current_version
            save_version(VERSION_FILE, self.version_data)

            # Update the hash of the file
            self.current_hash = self.update_info["hash"]
            self.version_data["hash"] = self.current_hash
            save_version(VERSION_FILE, self.version_data)

            self.info_label.config(text=f"Current Version: {self.current_version}")
            messagebox.showinfo("Update Applied", "Patch applied successfully, and version updated.")
            self.download_button.config(state=tk.DISABLED)
            self.apply_button.config(state=tk.DISABLED)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to apply the patch: {e}")

    def check_corruption_action(self):
        """Check for corruption and display the result."""
        check_file_corruption(TEXT_FILE, VERSION_FILE)

    def fix_corruption_action(self):
        """Fix corruption by requesting the file from the server."""
        handle_file_corruption(TEXT_FILE, VERSION_FILE)

# Run the GUI
if __name__ == "__main__":

    root = tk.Tk()
    app = UpdateClient(root)
    root.mainloop()
