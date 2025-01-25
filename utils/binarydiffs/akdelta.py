import zlib

def rolling_hash(data, base=257, mod=2**32):
    """
    Compute a simple rolling hash for the given data.
    """
    h = 0
    for byte in data:
        h = (h * base + byte) % mod
    return h

def generate_optimized_delta_patch(original_file_path, updated_file_path, patch_file_path):
    """
    Generate a delta patch using an optimized algorithm.
    """
    WINDOW_SIZE = 64  # Sliding window size
    BASE = 257
    MOD = 2**32

    # Read files into memory
    with open(original_file_path, "rb") as f:
        original_data = f.read()
    with open(updated_file_path, "rb") as f:
        updated_data = f.read()

    patch = []
    original_len = len(original_data)
    updated_len = len(updated_data)

    i, j = 0, 0

    # Sliding window algorithm
    while j < updated_len:
        match_found = False

        # Look for a match in the original file
        while i < original_len - WINDOW_SIZE:
            # Check if the hash of the current window matches
            if rolling_hash(original_data[i:i + WINDOW_SIZE], BASE, MOD) == rolling_hash(updated_data[j:j + WINDOW_SIZE], BASE, MOD):
                match_found = True
                break
            i += 1

        if match_found:
            # Record a COPY command
            patch.append(("COPY", i, WINDOW_SIZE))
            j += WINDOW_SIZE
        else:
            # Record an INSERT command
            patch.append(("INSERT", updated_data[j:j + 1]))
            j += 1

    # Save the patch to a file
    with open(patch_file_path, "wb") as f:
        f.write(zlib.compress(str(patch).encode()))

    print(f"Optimized delta patch generated and saved to {patch_file_path}")

def apply_optimized_delta_patch(original_file_path, patch_file_path):
    """
    Apply an optimized delta patch to an original file to produce the updated file.
    """
    with open(original_file_path, "rb") as f:
        original_data = f.read()

    # Load and decompress the patch
    with open(patch_file_path, "rb") as f:
        patch = eval(zlib.decompress(f.read()).decode())

    updated_data = bytearray()
    for command in patch:
        if command[0] == "COPY":
            # COPY command: copy data from the original file
            _, offset, length = command
            updated_data.extend(original_data[offset:offset + length])
        elif command[0] == "INSERT":
            # INSERT command: insert new data
            _, data = command
            updated_data.extend(data)

    # Write the updated data to a new file
    with open(original_file_path, "wb") as f:
        f.write(updated_data)

    print(f"Patched file created at {original_file_path}")
