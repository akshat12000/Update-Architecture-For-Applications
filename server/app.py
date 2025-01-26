from flask import Flask, request, jsonify, send_file
import os
import json
import hashlib
import sys

# Add the root directory (project directory) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.binarydiffs.akdelta import generate_optimized_delta_patch

# File paths
REPO_DIR = os.path.dirname(__file__) + "/repo"
TEXT_FILE = os.path.dirname(__file__) + "/repo/A.txt"
VERSION_FILE = os.path.dirname(__file__) + "/version.json"
PATCH_FOLDER = os.path.dirname(__file__) + "/patches"
OLD_VERSION_FILES_PATH = os.path.dirname(__file__) + "/repo/old"

app = Flask(__name__)

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
    return {"version": "0.0.0", "hash": ""}

def save_version(version_file, version_data):
    """Save version information to a JSON file."""
    with open(version_file, "w") as f:
        json.dump(version_data, f, indent=4)

def bump_version(version):
    """Increment the version number."""
    major, minor, patch = map(int, version.split("."))
    patch += 1
    return f"{major}.{minor}.{patch}"

def generate_patch(old_file, new_file, patch_file):
    """Generate a patch file."""
    generate_optimized_delta_patch(old_file, new_file, patch_file)

@app.route("/check_update/<file_name>", methods=["GET"])
def check_update(file_name):
    """Check for updates."""
    client_version = request.args.get("version")
    server_version_data = load_version(VERSION_FILE)

    # Check if the client version matches the server version
    for file in server_version_data:
        if file["file_name"] == file_name:
            server_version_data = file
            break

    if client_version == server_version_data["version"]:
        return jsonify({"update": False})
    else:
        return jsonify({
            "update": True,
            "version": server_version_data["version"],
            "hash": server_version_data["hash"],
            "patch_url": f"/get_patch/{file_name}_{server_version_data['version']}.patch"
        })

@app.route("/add-file-to-database/<file_name>", methods=["GET"])
def add_file_to_database(file_name):
    # add file to version.json (if file is present then don't do anything else add it)
    file_path = os.path.join(REPO_DIR, file_name)
    version_data = load_version(VERSION_FILE)
    # version_data is an array of objects with properties: file_name, version, hash
    # iterate over the array and check if file_name is present in any of the objects
    fPresent = False
    for file in version_data:
        if file["file_name"] == file_name:
            fPresent = True
            break
    if not fPresent:
        version_data.append({"file_name": file_name, "version": "1.0.0", "hash": calculate_file_hash(file_path)})
        save_version(VERSION_FILE, version_data)
        # create a copy of the file in the old directory
        with open(file_path, "r") as f:
            with open(f"{OLD_VERSION_FILES_PATH}/{file_name}.old", "w") as old:
                old.writelines(f.readlines())

        return jsonify({"message": "File added to the database."})
    return jsonify({"message": "File already present in the database."})

@app.route("/get_patch/<patch_name>", methods=["GET"])
def get_patch(patch_name):
    """Serve a patch file."""
    patch_path = os.path.join(PATCH_FOLDER, patch_name)
    if os.path.exists(patch_path):
        return send_file(patch_path, as_attachment=True)
    return jsonify({"error": "Patch not found"}), 404

@app.route("/update_file", methods=["GET"])
def update_file():
    """Update the server file and bump the version."""

    # we will do this for every file in the version.json
    version_data = load_version(VERSION_FILE)

    for file in version_data:
        file_name = file["file_name"]
        old_hash = file["hash"]
        file_path = os.path.join(REPO_DIR, file_name)
        new_hash = calculate_file_hash(os.path.join(REPO_DIR, file_name))

        if old_hash != new_hash:
            new_version = bump_version(file["version"])
            old_file = f"{OLD_VERSION_FILES_PATH}/{file_name}.old"
            generate_patch(old_file, file_path, f"{PATCH_FOLDER}/{file_name}_{new_version}.patch")
            # Copy the content of new file to old file
            with open(file_path, "r") as new, open(old_file, "w") as old:
                old.writelines(new.readlines())

            file["version"] = new_version
            file["hash"] = new_hash
            save_version(VERSION_FILE, version_data)

            return jsonify({"success": True, "new_version": new_version})
        
    return jsonify({"success": False, "message": "No changes detected."})

@app.route('/get_file', methods=['POST'])
def get_file():
    """API to return the requested file content."""
    data = request.json
    file_name = data.get("file_name")
    print(f"Requested file: {file_name}")
    # Build the full file path inside the repo directory
    file_path = os.path.join(REPO_DIR, file_name)
    print(f"Full file path: {file_path}")
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    # Read the file content
    with open(file_path, 'r') as f:
        file_content = f.read()

    # Include the current hash and version from version.json
    version_data = load_version(VERSION_FILE)
    for file in version_data:
        if file["file_name"] == file_name:
            version_data = file
            break

    return jsonify({
        "file_content": file_content,
        "version": version_data.get("version", 0),
        "hash": version_data.get("hash", "")
    })

@app.route("/sync_json_file", methods=["GET"])
def sync_json_file():
    """Sync the JSON file with the server."""
    # Read the JSON file content
    with open(VERSION_FILE, 'r') as f:
        file_content = f.read()

    return jsonify({"file_content": file_content})

if __name__ == "__main__":
    app.run(debug=True)