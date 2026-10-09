import os
import time
import zipfile
import requests

URL = "https://zenodo.org/api/records/4463683/files/Collision%20Avoidance%20Challenge%20-%20Dataset.zip/content"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
ESA_DIR = os.path.join(BASE_DIR, "esa")
ZIP_PATH = os.path.join(CACHE_DIR, "Collision_Avoidance_Challenge_Dataset.zip")
TARGET_SIZE = 221128642

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(ESA_DIR, exist_ok=True)


def download_with_retry():
    while True:
        current_size = os.path.getsize(ZIP_PATH) if os.path.exists(ZIP_PATH) else 0
        if current_size >= TARGET_SIZE:
            print(f"Zip already complete ({current_size} bytes).")
            break

        headers = {}
        if current_size > 0:
            headers["Range"] = f"bytes={current_size}-"
            print(f"Resuming download from byte {current_size} / {TARGET_SIZE}...")
        else:
            print(f"Starting download to {ZIP_PATH} ({TARGET_SIZE} bytes)...")

        try:
            with requests.get(URL, headers=headers, stream=True, timeout=30) as r:
                if r.status_code not in (200, 206):
                    print(f"Unexpected status code {r.status_code}, retrying in 5s...")
                    time.sleep(5)
                    continue

                mode = "ab" if current_size > 0 else "wb"
                with open(ZIP_PATH, mode) as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            current_size += len(chunk)
                            pct = (current_size / TARGET_SIZE) * 100
                            print(f"\rDownloaded {current_size / (1024*1024):.1f} MB / {TARGET_SIZE / (1024*1024):.1f} MB ({pct:.1f}%)", end="", flush=True)

            print()
            if os.path.getsize(ZIP_PATH) >= TARGET_SIZE:
                print("Download completed successfully.")
                break
        except Exception as e:
            print(f"\nDownload error: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    print(f"Extracting {ZIP_PATH} to {ESA_DIR}...")
    with zipfile.ZipFile(ZIP_PATH, "r") as z:
        z.extractall(ESA_DIR)
    print(f"Extraction complete. Files in {ESA_DIR}: {os.listdir(ESA_DIR)}")


if __name__ == "__main__":
    download_with_retry()
