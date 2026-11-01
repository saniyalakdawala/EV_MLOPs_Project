"""
Script to download official OSGeo PostGIS bundle for PostgreSQL 17 Windows x64.
"""
import urllib.request
import ssl
import os

URL = 'https://download.osgeo.org/postgis/windows/pg17/postgis-bundle-pg17-3.6.2x64.zip'
OUT_ZIP = 'data/postgis-bundle-pg17-3.6.2x64.zip'

def download():
    if os.path.exists(OUT_ZIP) and os.path.getsize(OUT_ZIP) > 100 * 1024 * 1024:
        print(f"PostGIS bundle already downloaded ({os.path.getsize(OUT_ZIP)} bytes).")
        return True
    
    print(f"Downloading PostGIS bundle from {URL}...")
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(URL, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, context=ctx) as resp, open(OUT_ZIP, 'wb') as out_f:
        total = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        chunk_size = 1024 * 1024
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            out_f.write(chunk)
            downloaded += len(chunk)
            if total:
                print(f"Progress: {downloaded / (1024*1024):.1f} MB / {total / (1024*1024):.1f} MB ({(downloaded/total)*100:.1f}%)", end='\r')
    print("\nDownload complete!")
    return True

if __name__ == '__main__':
    download()
