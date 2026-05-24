try:
    import requests
except ImportError:
    print("Error: El modulo 'requests' no esta instalado. Instalelo con 'pip install requests'.")
    exit(1)

import re
import os
import csv
import time
from urllib.parse import urlparse


# ====================== FUNCIONES BASICAS ======================

def check_write_permissions():
    current_dir = os.getcwd()
    test_file = os.path.join(current_dir, ".write_test.tmp")
    try:
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        return True
    except PermissionError:
        print("No tienes permisos de escritura en el directorio actual:")
        print(f"   {current_dir}")
        return False
    except Exception as e:
        print(f"Advertencia al verificar permisos de escritura: {e}")
        return True


def get_unique_folder_name(base_folder):
    if not os.path.exists(base_folder):
        return base_folder
    counter = 2
    while True:
        new_folder = f"{base_folder}_{counter}"
        if not os.path.exists(new_folder):
            return new_folder
        counter += 1


def extract_steam_id(url):
    pattern = r'id=(\d+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None


def get_with_retries(url, headers=None, retries=3, initial_delay=1):
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    delay = initial_delay
    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True, allow_redirects=True, timeout=15, headers=headers)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                if attempt == retries - 1:
                    raise requests.exceptions.RequestException(f"Codigo HTTP {response.status_code}")
                print(f"Aviso: Demasiadas peticiones. Esperando {delay} segundos...")
                time.sleep(delay)
                delay *= 2
                continue
            elif response.status_code == 403:
                print(f"Error 403 en {url}.")
                if attempt < retries - 1:
                    headers.pop('Referer', None)
                    time.sleep(delay)
                    continue
                raise
            else:
                raise requests.exceptions.RequestException(f"Codigo HTTP {response.status_code}")
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"Error en intento {attempt+1}/{retries}: {str(e)}. Reintentando...")
            time.sleep(delay)
   
    raise requests.exceptions.RequestException(f"No se pudo obtener la URL despues de {retries} intentos.")


def get_file_type_from_headers(response):
    content_type = response.headers.get('Content-Type', '').lower()
    if 'pdf' in content_type: return '.pdf'
    elif 'image/jpeg' in content_type or 'image/jpg' in content_type: return '.jpg'
    elif 'image/png' in content_type: return '.png'
    elif 'image/gif' in content_type: return '.gif'
    elif 'image/webp' in content_type: return '.webp'
    return None


def verify_header_signature(content):
    if len(content) < 8:
        return None

    if content.startswith(b'\xFF\xD8\xFF'): return '.jpg'
    if content.startswith(b'\x89PNG\r\n\x1a\n'): return '.png'
    if content.startswith(b'GIF87a') or content.startswith(b'GIF89a'): return '.gif'
    if content.startswith(b'RIFF') and content[8:12] == b'WEBP': return '.webp'
    if content.startswith(b'BM'): return '.bmp'
    if content.startswith(b'%PDF'): return '.pdf'
    if content.startswith(b'PK\x03\x04'): return '.zip'

    try:
        text = content[:512].decode('ascii', errors='ignore').lstrip()
        if text:
            first_line = text.splitlines()[0]
            if (first_line.startswith('#') or first_line.startswith('v ') or 
                first_line.startswith('f ') or 'mtllib' in text[:200] or 'o ' in text[:100]):
                return '.obj'
    except:
        pass
    return None


def get_clean_field_name(field_name):
    if field_name.lower() == "normalurl":
        return "FaceURL"
    return field_name


def clean_steam_url(url):
    if 'cloud-3.steamusercontent.com' in url.lower():
        return url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
    return url


# ====================== FUNCION DESCARGA ======================
def download_file(url, download_path, field_name, counter, total):
    try:
        parsed = urlparse(url)
        url_ext = os.path.splitext(parsed.path)[1].lower()

        response = get_with_retries(url)
        header_ext = get_file_type_from_headers(response)

        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) >= 1024:
                break

        signature_ext = verify_header_signature(content)

        clean_field = get_clean_field_name(field_name)
        field_lower = clean_field.lower()

        final_ext = None
        final_field_name = clean_field

        if "meshurl" in field_lower:
            final_ext = ".obj"
        elif "pdfurl" in field_lower or header_ext == '.pdf' or signature_ext == '.pdf':
            final_ext = ".pdf"
            final_field_name = "PDFURL"
        elif field_lower in ["faceurl", "backurl", "imageurl"]:
            if header_ext in {'.jpg','.jpeg','.png','.gif','.webp','.bmp'}:
                final_ext = header_ext
            elif signature_ext in {'.jpg','.png','.gif','.webp','.bmp'}:
                final_ext = signature_ext
            elif signature_ext == '.obj':
                final_ext = '.obj'
                final_field_name = "MeshURL"
            else:
                final_ext = url_ext if url_ext in {'.jpg','.jpeg','.png','.gif','.webp','.bmp'} else signature_ext
        else:
            if header_ext == '.pdf' or signature_ext == '.pdf':
                final_ext = '.pdf'
                final_field_name = "PDFURL"
            elif signature_ext == '.obj':
                final_ext = '.obj'
                final_field_name = "MeshURL"
            else:
                final_ext = header_ext or signature_ext or url_ext

        allowed_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.pdf', '.obj'}
        if not final_ext or final_ext not in allowed_exts:
            return False, None, clean_field

        filename = f"{final_field_name}_{counter}{final_ext}"

        file_path = os.path.join(download_path, filename)
        c = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{c}{ext}"
            file_path = os.path.join(download_path, filename)
            c += 1

        with open(file_path, 'wb') as f:
            f.write(content)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"{counter:3d}/{total} | {final_field_name:<20} -> {filename}")
        return True, filename, final_field_name

    except Exception as e:
        status_code = "ERROR"
        if hasattr(e, 'response') and e.response:
            status_code = str(e.response.status_code)
        elif "HTTP" in str(e):
            status_code = str(e).split()[-1]
        
        print(f"{counter:3d}/{total} | {field_name} -> {status_code} | URL: {url}")
        return False, None, field_name


# ====================== MAIN ======================
def main():
    print("=== Tabletop Simulator URL Descargador ===\n")
    
    workshop_id = None
    workshop_title = "Desconocido"

    if not check_write_permissions():
        input("\nPresiona Enter para salir...")
        return

    workshop_url = input("Ingrese la URL del Workshop de Steam: ").strip()

    if not workshop_url.startswith("https://steamcommunity.com/sharedfiles/filedetails"):
        print("ERROR: La URL debe comenzar con:")
        print("   https://steamcommunity.com/sharedfiles/filedetails")
        input("\nPresiona Enter para salir...")
        return

    workshop_id = extract_steam_id(workshop_url)
    
    if not workshop_id:
        print("Error: No se pudo extraer un ID valido de la URL.")
        input("\nPresiona Enter para salir...")
        return

    api_url = f"https://www.steamworkshopdownloader.cc/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
    
    try:
        response = requests.get(api_url, timeout=30)
        data = response.json()
        workshop_title = data.get("title", "WorkshopItem")
        download_url = data.get("download_url")

        print(f"Obteniendo informacion del Workshop: {workshop_id} titulo: {workshop_title}...")
        
        safe_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', workshop_title)
        base_path = os.path.join(os.getcwd(), safe_folder_name)
        download_path = get_unique_folder_name(base_path)

        os.makedirs(download_path, exist_ok=True)

        print(f"Guardando archivos en: {download_path}\n")

        workshop_response = get_with_retries(download_url)
        bin_path = os.path.join(download_path, f"{workshop_id}.bin")
        with open(bin_path, 'wb') as f:
            f.write(workshop_response.content)
        
    except Exception as e:
        print(f"Error al obtener informacion del workshop: {e}")
        input("\nPresiona Enter para salir...")
        return

    # ==================== BUSQUEDA DE URLS ====================
    print("Buscando URLs dentro del archivo...")
    try:
        with open(bin_path, 'rb') as f:
            text = f.read().decode('utf-8', errors='ignore')

        # Regex balanceado (menos estricto que antes)
        pattern = r'([A-Za-z0-9_]+URL)\x00.*?(https?://[^\x00]+?)\x00'
        matches = re.finditer(pattern, text, re.IGNORECASE)

        seen = set()
        to_download = []

        for match in matches:
            field_name = match.group(1)
            url = match.group(2).strip()

            if not url.startswith(('http://', 'https://')) or url in seen or len(url) < 10:
                continue

            seen.add(url)
            to_download.append((field_name, url))

        print(f"Se encontraron {len(to_download)} URL validas para descargar.")

    except Exception as e:
        print(f"No se pudo procesar el archivo .bin: {e}")
        to_download = []

    # ==================== DESCARGAS ====================
    print("\nIniciando descargas...\n")
    csv_rows = []
    successful = failed = 0
    total = len(to_download)

    for counter, (field_name, url) in enumerate(to_download, start=1):
        clean_url = clean_steam_url(url)
        success, filename, clean_field = download_file(clean_url, download_path, field_name, counter, total)
        
        if success:
            successful += 1
            csv_rows.append([clean_field, clean_url])
        else:
            failed += 1
        
        time.sleep(0.6)

    try:
        os.remove(bin_path)
    except:
        pass

    # Guardar CSV
    if 'download_path' in locals() and download_path:
        csv_path = os.path.join(download_path, f"{workshop_id or 'unknown'}_urls.csv")
        try:
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                csv.writer(f, delimiter=';').writerows(csv_rows)
            print(f"\nCSV creado: {os.path.basename(csv_path)}")
        except Exception as e:
            print(f"Error al guardar CSV: {e}")

    # ==================== RESUMEN FINAL ====================
    print("\n" + "="*60)
    print("                     RESUMEN FINAL")
    print("="*60)
    print(f"Workshop ID         : {workshop_id}")
    print(f"Nombre del mod      : {workshop_title}")
    print(f"URLs encontradas    : {len(to_download)}")
    print(f"Descargadas         : {successful}")
    print(f"Fallidas            : {failed}")
    if 'download_path' in locals() and download_path:
        print(f"Directorio de descarga : {download_path}")
    print("="*60)


if __name__ == "__main__":
    main()
