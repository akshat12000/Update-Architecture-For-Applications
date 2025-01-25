from flask import Flask, request, jsonify, send_file
import os
import json
import hashlib
import difflib

# File paths
BASE_DIR = './server'
REPO_DIR = "repo"
TEXT_FILE = "repo/A.txt"
VERSION_FILE = "version.json"
PATCH_FOLDER = "patches"

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
    with open(old_file, "r") as old, open(new_file, "r") as new:
        diff = difflib.unified_diff(old.readlines(), new.readlines(), lineterm='')
    with open(patch_file, "w") as patch:
        patch.writelines(line + '\n' for line in diff)

@app.route("/check_update", methods=["GET"])
def check_update():
    """Check for updates."""
    client_version = request.args.get("version")
    server_version_data = load_version(VERSION_FILE)

    if client_version == server_version_data["version"]:
        return jsonify({"update": False})
    else:
        return jsonify({
            "update": True,
            "version": server_version_data["version"],
            "hash": server_version_data["hash"],
            "patch_url": f"/get_patch/{server_version_data['version']}.patch"
        })

@app.route("/get_patch/<patch_name>", methods=["GET"])
def get_patch(patch_name):
    """Serve a patch file."""
    patch_path = os.path.join(PATCH_FOLDER, patch_name)
    if os.path.exists(patch_path):
        return send_file(patch_path)
    return jsonify({"error": "Patch not found"}), 404

@app.route("/update_file", methods=["GET"])
def update_file():
    """Update the server file and bump the version."""
    version_data = load_version(VERSION_FILE)
    old_hash = version_data.get("hash", "")
    new_hash = calculate_file_hash(TEXT_FILE)

    if old_hash != new_hash:
        new_version = bump_version(version_data["version"])
        old_file = f"{TEXT_FILE}.old"
        generate_patch(old_file, TEXT_FILE, f"{PATCH_FOLDER}/{new_version}.patch")
        # Copy the content of new file to old file
        with open(TEXT_FILE, "r") as new, open(old_file, "w") as old:
            old.writelines(new.readlines())

        version_data["version"] = new_version
        version_data["hash"] = new_hash
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
    return jsonify({
        "file_content": file_content,
        "version": version_data.get("version", 0),
        "hash": version_data.get("hash", "")
    })

if __name__ == "__main__":
    app.run(debug=True)