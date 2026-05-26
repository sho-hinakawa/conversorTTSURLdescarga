try:
    import requests
except ImportError:
    print("Error: El modulo 'requests' no esta instalado. Instalelo con 'pip install requests'.")
    exit(1)

import re
import os
import csv
import time
from urllib.parse import urlparse, unquote


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
    except Exception:
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


def get_with_retries(url, session, headers=None, retries=5, initial_delay=0.8):
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    delay = initial_delay
    for attempt in range(retries):
        try:
            response = session.get(url, stream=True, allow_redirects=True, timeout=25, headers=headers)
            
            if response.status_code == 200:
                return response
            elif response.status_code == 404:
                print(f"   404 No encontrado: {url}")
                return None
            elif response.status_code == 429:
                print(f"   Demasiadas peticiones (429). Esperando {delay}s...")
                time.sleep(delay)
                delay *= 1.4
                continue
            else:
                print(f"   HTTP {response.status_code} en {url}")
                
        except Exception as e:
            print(f"   Error en intento {attempt+1}: {str(e)[:60]}")
        
        if attempt < retries - 1:
            time.sleep(delay)
            delay *= 1.4
    
    return None


def get_clean_field_name(field_name):
    if field_name.lower() == "normalurl":
        return "FaceURL"
    return field_name


def clean_steam_url(url):
    url = url.strip()
    if 'cloud-3.steamusercontent.com' in url.lower():
        return url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
    if url.startswith('http://steamusercontent'):
        return url.replace('http://', 'https://')
    return url


def get_url_extension(url):
    if not url:
        return ""
    url = unquote(url)
    parsed = urlparse(url)
    path = parsed.path
    if '?' in path:
        path = path.split('?')[0]
    ext = os.path.splitext(path)[1].lower()
    return ext


# ====================== DESCARGA ======================
def download_file(url, download_path, field_name, counter, total, csv_writer, csv_file, session):
    try:
        url_ext = get_url_extension(url)
        clean_field = get_clean_field_name(field_name)

        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp', '.pdf', '.obj'}

        if url_ext and url_ext not in valid_extensions and url_ext != ".bin":
            print(f"{counter:3d}/{total} | {clean_field:<20} -> {url_ext} (omitiendo)")
            csv_writer.writerow([clean_field, url, f"OMITIDO ({url_ext})"])
            csv_file.flush()
            return "invalid", clean_field

        response = get_with_retries(url, session)
        if response is None:
            csv_writer.writerow([clean_field, url, "ERROR (descarga fallida)"])
            csv_file.flush()
            return "failed", clean_field

        content = b''
        for chunk in response.iter_content(chunk_size=16384):
            content += chunk
            if len(content) >= 1024:
                break

        signature_ext = None
        if content.startswith(b'\xFF\xD8\xFF'): signature_ext = '.jpg'
        elif content.startswith(b'\x89PNG\r\n\x1a\n'): signature_ext = '.png'
        elif content.startswith(b'%PDF'): signature_ext = '.pdf'
        elif content.startswith(b'BM'): signature_ext = '.bmp'

        field_lower = clean_field.lower()

        if signature_ext == '.obj' or url_ext == '.obj' or "meshurl" in field_lower:
            final_ext = ".obj"
            final_field = "MeshURL"
        elif signature_ext == '.pdf' or url_ext == '.pdf' or "pdfurl" in field_lower:
            final_ext = ".pdf"
            final_field = "PDFURL"
        else:
            final_ext = signature_ext or url_ext
            final_field = clean_field

        if not final_ext or final_ext not in valid_extensions:
            print(f"{counter:3d}/{total} | {clean_field:<20} -> Extension invalida (omitiendo)")
            csv_writer.writerow([clean_field, url, "INVALIDA"])
            csv_file.flush()
            return "invalid", clean_field

        filename = f"{final_field}_{counter}{final_ext}"
        file_path = os.path.join(download_path, filename)

        c = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            filename = f"{name}_{c}{ext}"
            file_path = os.path.join(download_path, filename)
            c += 1

        with open(file_path, 'wb') as f:
            f.write(content)
            for chunk in response.iter_content(chunk_size=16384):
                if chunk:
                    f.write(chunk)

        print(f"{counter:3d}/{total} | {final_field:<20} -> {filename}")
        csv_writer.writerow([final_field, url, filename])
        csv_file.flush()
        return "success", final_field

    except Exception as e:
        print(f"{counter:3d}/{total} | {field_name:<20} -> Error: {str(e)[:70]}")
        csv_writer.writerow([field_name, url, f"ERROR: {str(e)[:70]}"])
        csv_file.flush()
        return "failed", field_name


# ====================== OBTENER WORKSHOP ======================
def get_workshop_data(workshop_id):
    # Prioridad a GET simples
    alternatives = [
        f"https://www.steamworkshopdownloader.cc/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
        f"https://steamworkshopdownloader.net/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
        f"https://steamworkshopdownloader.top/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}",
    ]

    for api_url in alternatives:
        print(f"Intentando GET: {api_url.split('/')[2]}...")
        try:
            response = requests.get(api_url, timeout=25)
            if response.status_code == 200:
                data = response.json()
                title = data.get("title", "WorkshopItem")
                download_url = data.get("download_url")
                if download_url:
                    print(f"Exito con {api_url.split('/')[2]}")
                    return title, download_url
        except Exception as e:
            print(f"   Fallo: {str(e)[:80]}")
            continue

    return None, None


# ====================== MAIN ======================
def main():
    print("=== Tabletop Simulator URL Descargador ===\n")
    
    if not check_write_permissions():
        input("\nPresiona Enter para salir...")
        return

    workshop_url = input("Ingrese la URL del Workshop de Steam: ").strip()
    workshop_id = extract_steam_id(workshop_url)
    if not workshop_id:
        print("Error: No se pudo extraer el ID del workshop.")
        input("\nPresiona Enter para salir...")
        return

    print("Procesando Workshop")
    print(f"ID: {workshop_id}\n")

    workshop_title, download_url = get_workshop_data(workshop_id)

    if not download_url:
        print("\nError: Ningun downloader GET funciono.")
        print("Prueba mas tarde o revisa tu conexion.")
        input("\nPresiona Enter para salir...")
        return

    print(f"Titulo: {workshop_title}\n")

    safe_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', workshop_title)
    base_path = os.path.join(os.getcwd(), safe_folder_name)
    download_path = get_unique_folder_name(base_path)

    os.makedirs(download_path, exist_ok=True)
    print(f"Guardando en: {download_path}\n")

    try:
        workshop_response = requests.get(download_url, timeout=60)
        bin_path = os.path.join(download_path, f"{workshop_id}.bin")
        with open(bin_path, 'wb') as f:
            f.write(workshop_response.content)
    except Exception as e:
        print(f"Error al descargar el .bin: {e}")
        input("\nPresiona Enter para salir...")
        return

    print("Buscando todas las URLs en el archivo...")
    with open(bin_path, 'rb') as f:
        text = f.read().decode('utf-8', errors='ignore')

    pattern = r'([A-Za-z0-9_]+URL)\x00.*?(https?://[^\x00]+?)\x00'
    matches = re.finditer(pattern, text, re.IGNORECASE)

    seen = set()
    to_download = []

    for match in matches:
        field_name = match.group(1)
        url = match.group(2).strip()
        if (url.startswith(('http://', 'https://')) and url not in seen and len(url) > 15):
            seen.add(url)
            to_download.append((field_name, url))

    print(f"Se encontraron {len(to_download)} URLs para procesar.\n")

    csv_path = os.path.join(download_path, f"{workshop_id}_urls.csv")
    csv_file = open(csv_path, 'w', encoding='utf-8-sig', newline='')
    csv_writer = csv.writer(csv_file, delimiter=';')
    csv_writer.writerow(['Campo', 'URL', 'Archivo'])
    csv_file.flush()

    print("Iniciando descargas...\n")
    successful = 0
    invalid_ext = 0
    failed = 0
    total = len(to_download)
    
    sleep_time = 0.15
    session = requests.Session()

    for counter, (field_name, url) in enumerate(to_download, start=1):
        clean_url = clean_steam_url(url)
        result, clean_field = download_file(
            clean_url, download_path, field_name, counter, total, 
            csv_writer, csv_file, session
        )
        
        if result == "success":
            successful += 1
        elif result == "invalid":
            invalid_ext += 1
        elif result == "failed":
            failed += 1
            
        time.sleep(sleep_time)

    csv_file.close()
    try:
        os.remove(bin_path)
    except:
        pass

    print("\n" + "="*80)
    print("                     RESUMEN FINAL")
    print("="*80)
    print(f"Workshop ID                         : {workshop_id}")
    print(f"Nombre del mod                      : {workshop_title}")
    print(f"Directorio                          : {download_path}")
    print(f"URLs encontradas                    : {len(to_download)}")
    print(f"Descargadas (validas)               : {successful}")
    print(f"Eliminadas (extension invalida)     : {invalid_ext}")
    print(f"Fallidas (error de descarga)        : {failed}")
    print(f"CSV generado                        : {os.path.basename(csv_path)}")
    print("="*80)


if __name__ == "__main__":
    main()
