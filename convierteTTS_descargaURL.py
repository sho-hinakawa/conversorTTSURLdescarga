try:
    import requests
except ImportError:
    print("Error: El modulo 'requests' no esta instalado. Instalelo con 'pip install requests'.")
    exit(1)

import re
import os
import csv
import mimetypes
import time
import shutil
from urllib.parse import urlparse

# Funcion para extraer el ID de una URL de Steam Community
def extract_steam_id(url):
    pattern = r'id=(\d+)'
    match = re.search(pattern, url)
    return match.group(1) if match else None

# Limpia una URL eliminando espacios en blanco
def clean_url(url):
    try:
        return url.strip()
    except Exception as e:
        print(f"Error al limpiar URL {url}: {str(e)}")
        return None

# Reemplaza URLs especificas en una lista de URLs y guarda el resultado en un CSV temporal
def replace_urls_in_csv(urls, output_filename, download_path):
    archivo_salida_csv = os.path.join(download_path, output_filename)
    
    if not os.access(download_path, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {download_path}"
        print(error_message)
        return None, 0
    
    try:
        if not urls:
            error_message = "La lista de URLs esta vacia."
            print(error_message)
            return None, 0
        
        urls_vistas = set()
        filas_reemplazadas = []
        
        for i, (patron, url) in enumerate(urls, start=1):
            if 'cloud-3.steamusercontent.com' in url.lower():
                url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
            else:
                url_modificada = url
            
            if url_modificada not in urls_vistas:
                urls_vistas.add(url_modificada)
                filas_reemplazadas.append([patron, url_modificada])
        
        with open(archivo_salida_csv, 'w', encoding='utf-8-sig', newline='') as archivo_salida:
            escritor_csv = csv.writer(archivo_salida)
            if filas_reemplazadas:
                escritor_csv.writerows(filas_reemplazadas)
            else:
                escritor_csv.writerow(["Mensaje", "No se encontraron URLs validas o todas eran duplicadas"])
        
        print("\nResumen de procesamiento:")
        print(f"Filas procesadas: {len(urls)}")
        print(f"Reemplazos realizados: {len(filas_reemplazadas)}")
        
        return archivo_salida_csv, len(filas_reemplazadas)

    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
        print(f"Error: {error_message}")
        return None, 0

# Verifica la accesibilidad de una URL y obtiene su contenido
def verify_and_fetch_url(url):
    retries = 5
    delay = 10  # segundos
    parsed_url = urlparse(url)
    netloc = parsed_url.netloc.lower()
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'image/*,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5'
    }
    
    if netloc.startswith('steamcommunity.com') or netloc.startswith('steamusercontent.com'):
        headers['Referer'] = 'https://steamcommunity.com/'
    elif netloc.startswith('i.imgur.com'):
        headers['Referer'] = 'https://imgur.com/'
    
    for attempt in range(retries):
        try:
            response = requests.get(url, stream=True, allow_redirects=True, timeout=15, headers=headers)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                if attempt == retries - 1:
                    raise requests.exceptions.RequestException(f"Codigo HTTP {response.status_code}: Demasiadas peticiones")
                print(f"Aviso: Demasiadas peticiones al servidor ({url}). Esperando {delay} segundos...")
                time.sleep(delay)
                delay *= 2
                continue
            elif response.status_code == 403:
                print(f"Error 403 en {url}. Posible restricción del servidor.")
                if attempt < retries - 1 and 'Referer' in headers:
                    print(f"Reintentando sin Referer para {url}...")
                    headers.pop('Referer', None)
                    time.sleep(delay)
                    continue
                raise requests.exceptions.RequestException(f"Codigo HTTP 403")
            else:
                raise requests.exceptions.RequestException(f"Codigo HTTP {response.status_code} para {url}")
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise requests.exceptions.RequestException(f"Error final al verificar URL {url} tras {retries} intentos: {str(e)}")
            print(f"Error en intento {attempt+1}/{retries} para URL {url}: {str(e)}. Reintentando en {delay} segundos...")
            time.sleep(delay)
    
    raise requests.exceptions.RequestException(f"No se pudo obtener la URL {url} despues de {retries} intentos.")

# Determina la extension de un archivo basado en el tipo MIME de los encabezados
def get_file_extension(file_path, headers):
    content_type = headers.get('content-type')
    if content_type:
        extension = mimetypes.guess_extension(content_type)
        if extension:
            return extension
    return None

MIME_TO_EXTENSION = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'model/obj': '.obj',
    'text/plain': '.obj',
    'application/octet-stream': '.obj',
    'application/pdf': '.pdf'
}

HEADER_SIGNATURES = {
    'image/jpeg': b'\xFF\xD8\xFF',
    'image/png': b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A',
    'application/pdf': b'%PDF-',
    'model/obj': ['#', 'v ', 'f ', 'mtllib ', 'o ', 'g ', '\n', '\r\n', '\t', ' '],
    'text/plain': ['#', 'v ', 'f ', 'mtllib ', 'o ', 'g ', '\n', '\r\n', '\t', ' '],
    'application/octet-stream': ['#', 'v ', 'f ', 'mtllib ', 'o ', 'g ', '\n', '\r\n', '\t', ' ']
}

# Verifica la firma de cabecera de un archivo para determinar su tipo y extension
def verify_header_signature(content, pattern):
    try:
        if content.startswith(b'\xFF\xD8\xFF'):
            return 'image/jpeg', '.jpg'
        if content.startswith(b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A'):
            return 'image/png', '.png'
        if content.startswith(b'%PDF-'):
            return 'application/pdf', '.pdf'
        
        if pattern == 'MeshURL':
            try:
                text = content[:1024].decode('ascii')
                if not all(c.isprintable() or c in '\n\r\t ' for c in text):
                    return None, None
                text = text.lstrip()
                if not text:
                    return None, None
                if any(text.startswith(header) for header in HEADER_SIGNATURES['model/obj']):
                    return 'model/obj', '.obj'
                return None, None
            except UnicodeDecodeError:
                return None, None
        
        return None, None
    except Exception as e:
        print(f"Error al verificar firma de cabecera: {str(e)}")
        return None, None

# Descarga un archivo desde una URL y lo guarda en el directorio especificado
def download_file(url, download_path, index, pattern):
    try:
        if not url.startswith(('http://', 'https://')):
            error_message = f"URL invalida (no comienza con http:// o https://): {url}"
            print(error_message)
            return False, error_message, False
        
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        name, url_extension = os.path.splitext(os.path.basename(parsed_url.path))
        
        try:
            response = verify_and_fetch_url(url)
        except requests.exceptions.RequestException as e:
            return False, str(e), False
        
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content += chunk
                if len(content) >= 1024:
                    break
        
        content_type = response.headers.get('content-type', '').lower().split(';')[0]
        
        detected_mime_type, signature_extension = verify_header_signature(content, pattern)
        
        if pattern in ['FaceURL', 'BackURL']:
            if url_extension.lower() == '.bin':
                if detected_mime_type not in ['image/jpeg', 'image/png']:
                    error_message = f"Extension .bin no permitida para {pattern}, firma no es imagen: {url}"
                    print(error_message)
                    return False, error_message, False
                url_extension = signature_extension
            elif detected_mime_type not in ['image/jpeg', 'image/png']:
                error_message = f"Firma no valida para {pattern}: {detected_mime_type or 'desconocido'}: {url}"
                print(error_message)
                return False, error_message, False
        
        if pattern:
            if pattern == 'MeshURL':
                if detected_mime_type != 'model/obj' and content_type not in ['model/obj', 'text/plain', 'application/octet-stream']:
                    error_message = f"Firma o tipo MIME no valido para MeshURL: {detected_mime_type or content_type}: {url}"
                    print(error_message)
                    return False, error_message, False
                filename = f"{pattern}_{index}.obj"
            elif pattern == 'PDFUrl':
                if detected_mime_type != 'application/pdf' and content_type not in ['application/pdf']:
                    error_message = f"Firma o tipo MIME no valido para PDFUrl: {detected_mime_type or content_type}: {url}"
                    print(error_message)
                    return False, error_message, False
                filename = f"{pattern}_{index}.pdf"
            elif pattern in ['FaceURL', 'BackURL']:
                filename = f"{pattern}_{index}{signature_extension}"
            else:
                filename = f"{pattern}_{index}"
                if detected_mime_type and signature_extension:
                    filename = f"{pattern}_{index}{signature_extension}"
        else:
            if not filename or len(filename) > 100:
                filename = f"file_{index}"
            else:
                name, ext = os.path.splitext(filename)
                if detected_mime_type and signature_extension:
                    filename = f"{name}_{index}{signature_extension}"
                elif not ext:
                    filename = f"{name}_{index}"
                else:
                    filename = f"{name}_{index}{ext}"
        
        if pattern not in ['MeshURL', 'PDFUrl', 'FaceURL', 'BackURL']:
            new_extension = get_file_extension(None, response.headers)
            if url_extension and url_extension.lower() != '.bin' and url_extension.lower() in [ext.lower() for ext in MIME_TO_EXTENSION.values()]:
                filename = f"{name}_{index}{url_extension}"
            elif not new_extension and not signature_extension:
                error_message = f"Sin extension valida detectada: {url}"
                print("Omitiendo archivo")
                return False, error_message, True
            elif new_extension == '.bin' and not signature_extension:
                error_message = f"Archivo seria nombrado como .bin: {url}"
                print("Omitiendo archivo")
                return False, error_message, True
        
        file_path = os.path.join(download_path, filename)
        counter = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            name = name.rsplit('_', 1)[0]
            filename = f"{name}_{index}_{counter}{ext}"
            file_path = os.path.join(download_path, filename)
            counter += 1
        
        with open(file_path, 'wb') as f:
            f.write(content)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if pattern not in ['MeshURL', 'PDFUrl', 'FaceURL', 'BackURL']:
            name, url_extension = os.path.splitext(os.path.basename(parsed_url.path))
            if not url_extension or url_extension.lower() not in [ext.lower() for ext in MIME_TO_EXTENSION.values()]:
                name, ext = os.path.splitext(filename)
                new_extension = get_file_extension(file_path, response.headers)
                if not new_extension and not signature_extension:
                    os.remove(file_path)
                    error_message = f"No se pudo determinar la extension del archivo: {url}"
                    print("Omitiendo archivo")
                    return False, error_message, True
                if new_extension and not signature_extension and new_extension != '.bin':
                    new_filename = f"{name}{new_extension}"
                    new_file_path = os.path.join(download_path, new_filename)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{name}_{counter}{new_extension}"
                        new_file_path = os.path.join(download_path, new_filename)
                        counter += 1
                    try:
                        os.rename(file_path, new_file_path)
                    except OSError as e:
                        error_message = f"Error al renombrar archivo de {file_path} a {new_file_path}: {str(e)}"
                        print(error_message)
                        os.remove(file_path)
                        return False, error_message, True
                    file_path = new_file_path
                    filename = new_filename
        
        return True, filename, False
            
    except Exception as e:
        error_message = f"Error al descargar {url}: {str(e)}"
        print(error_message)
        return False, error_message, False

# Punto de entrada principal del script
def main():
    print("=== Tabletop Simulator URL Descargador ===")
    
    workshop_url = input("Ingrese la URL del Workshop de Steam: ").strip()
    workshop_id = extract_steam_id(workshop_url)
    if not workshop_id:
        print("Error: No se pudo extraer un ID valido de la URL proporcionada.")
        return

    # Construir URL de la API y obtener informacion
    api_url = f"https://www.steamworkshopdownloader.cc/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
    
    try:
        print(f"Obteniendo informacion para el ID: {workshop_id}...")
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        workshop_title = data.get("title", "WorkshopItem")
        download_url = data.get("download_url")

        if not download_url:
            print("Error: No se pudo obtener la URL de descarga desde la API.")
            return

        # Crear un nombre de directorio valido a partir del titulo del workshop
        safe_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', data.get("title", "WorkshopItem_Archivos"))
        download_path = os.path.join(os.getcwd(), safe_folder_name)
        workshop_binary_path = os.path.join(download_path, f"{workshop_id}")

        # Eliminar el directorio si ya existe
        if os.path.exists(download_path):
            try:
                shutil.rmtree(download_path)
                print(f"Directorio existente '{download_path}' eliminado.")
            except OSError as e:
                error_message = f"No se pudo eliminar el directorio existente '{download_path}': {str(e)}"
                print(f"Error: {error_message}")
                return

        # Crear el directorio de descarga
        try:
            os.makedirs(download_path, exist_ok=True)
            os.chmod(download_path, 0o777)
        except OSError as e:
            error_message = f"No se pudo crear o modificar permisos del directorio {download_path}: {str(e)}"
            print(f"Error: {error_message}")
            return

        # Verificar permisos de escritura en el directorio
        if not os.access(download_path, os.W_OK):
            error_message = f"No se tienen permisos de escritura en el directorio {download_path}"
            print(error_message)
            return

        print(f"Los archivos se guardaran en: {download_path}")
        
        # Descargar el archivo principal
        print(f"Descargando archivo principal de '{workshop_title}'...")
        workshop_response = requests.get(download_url, timeout=60)
        workshop_response.raise_for_status()

        with open(workshop_binary_path, 'wb') as f:
            f.write(workshop_response.content)

    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API o descargar el archivo principal: {e}")
        return
    except json.JSONDecodeError:
        print("Error: La respuesta de la API no es un JSON valido.")
        return
    
    # Extraer URLs directamente del archivo binario
    try:
        with open(workshop_binary_path, 'rb') as file:
            content = file.read()
        try:
            text = content.decode('utf-8', errors='ignore')
        except UnicodeDecodeError as e:
            error_message = f"Error al decodificar el archivo {workshop_binary_path}: {str(e)}"
            print(f"Error: {error_message}")
            if os.path.exists(workshop_binary_path):
                try:
                    os.remove(workshop_binary_path)
                except OSError as e:
                    print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
            return
        url_patterns = [
            (r'FaceURL\x00.*?(http[^\x00]+)\x00', 'FaceURL'),
            (r'BackURL\x00.*?(http[^\x00]+)\x00', 'BackURL'),
            (r'MeshURL\x00.*?(http[^\x00]+)\x00', 'MeshURL'),
            (r'PDFUrl\x00.*?(http[^\x00]+)\x00', 'PDFUrl'),
            (r'ImageURL\x00.*?(http[^\x00]+)\x00', 'ImageURL'),
            (r'ImageSecondaryURL\x00.*?(http[^\x00]+)\x00', 'ImageSecondaryURL'),
            (r'AssetbundleURL\x00.*?(http[^\x00]+)\x00', 'AssetbundleURL'),
            (r'AssetbundleSecondaryURL\x00.*?(http[^\x00]+)\x00', 'AssetbundleSecondaryURL'),
            (r'DiffuseURL\x00.*?(http[^\x00]+)\x00', 'DiffuseURL')
        ]
        seen_urls = set()
        urls = []
        for pattern, url_type in url_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                url = match.group(1).strip()
                cleaned_url = clean_url(url)
                if (cleaned_url and 
                    (cleaned_url.startswith('http://') or cleaned_url.startswith('https://')) and 
                    '.' in cleaned_url and 
                    not any(word in cleaned_url.lower() for word in ['function', 'end', 'if', 'then', 'else', 'lua'])):
                    if cleaned_url not in seen_urls:
                        seen_urls.add(cleaned_url)
                        urls.append((url_type, cleaned_url))
        unique_urls = list(dict.fromkeys(urls))
        converted_urls_count = len(unique_urls)
        if not unique_urls:
            error_message = "No se encontraron URLs validas"
            print(error_message)
            if os.path.exists(workshop_binary_path):
                try:
                    os.remove(workshop_binary_path)
                except OSError as e:
                    print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
            return
        print(f"Se extrajeron {converted_urls_count} URLs unicas.")
    except FileNotFoundError:
        error_message = f"El archivo {workshop_binary_path} no se encuentra."
        print(f"Error: {error_message}")
        if os.path.exists(workshop_binary_path):
            try:
                os.remove(workshop_binary_path)
            except OSError as e:
                print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
        return
    output_csv2 = f"{workshop_id}_replaced.csv"
    output_csv2_path, replacements_made = replace_urls_in_csv(unique_urls, output_csv2, download_path)
    if not output_csv2_path:
        error_message = "Error en el reemplazo de URLs. Proceso terminado."
        print(error_message)
        if os.path.exists(workshop_binary_path):
            try:
                os.remove(workshop_binary_path)
            except OSError as e:
                print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
        return
    print(f"Se realizaron {replacements_made} reemplazos de URLs.")
    try:
        # Leer el archivo CSV para descargar los archivos
        with open(output_csv2_path, 'r', encoding='utf-8-sig') as input_file:
            reader_csv = csv.reader(input_file)
            urls = list(reader_csv)
        if not urls:
            error_message = "El archivo CSV con URLs para descargar esta vacio."
            print(error_message)
            if os.path.exists(workshop_binary_path):
                try:
                    os.remove(workshop_binary_path)
                except OSError as e:
                    print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
            return
        # Crear archivo TXT con solo las URLs
        output_txt = f"{workshop_id}_replaced.txt"
        output_txt_path = os.path.join(download_path, output_txt)
        try:
            with open(output_csv2_path, 'r', encoding='utf-8-sig') as csv_file:
                reader_csv = csv.reader(csv_file)
                urls_for_txt = [row[1] for row in reader_csv if len(row) >= 2 and row[1]]
            with open(output_txt_path, 'w', encoding='utf-8', newline='') as txt_file:
                if urls_for_txt:
                    txt_file.write('\n'.join(urls_for_txt))
                else:
                    txt_file.write("No se encontraron URLs validas en el CSV")
        except Exception as e:
            error_message = f"Error al generar el archivo TXT {output_txt_path}: {str(e)}"
            print(f"Error: {error_message}")
        successful_downloads = 0
        failed_downloads = 0
        skipped_files = 0
        for index, row in enumerate(urls, start=1):
            if len(row) < 2:
                error_message = f"Fila invalida en el CSV (menos de 2 columnas): {row}"
                print(error_message)
                continue
            pattern, url = row[0], row[1]
            if not url:
                error_message = f"URL vacia para el patron {pattern}"
                print(error_message)
                continue
            success, result, skipped = download_file(url, download_path, index, pattern)
            if success:
                successful_downloads += 1
                print(f"Descargado ({successful_downloads}/{len(urls)}): {result}")
            elif skipped:
                skipped_files += 1
            else:
                failed_downloads += 1
            time.sleep(1) # Pausa de 1 segundo para no saturar el servidor
        # Si no hubo descargas exitosas, eliminar archivos TXT y CSV
        if successful_downloads == 0:
            for file_path in [output_txt_path, output_csv2_path]:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        print(f"Archivo '{file_path}' eliminado debido a que no hubo descargas exitosas.")
                    except OSError as e:
                        print(f"No se pudo eliminar el archivo '{file_path}': {e}")
        print("\n=== Resumen Final ===")
        print(f"Workshop ID procesado: {workshop_id}")
        print(f"Nombre Mod TTS: {workshop_title}")
        print(f"URLs extraidas: {converted_urls_count}")
        print(f"Reemplazos realizados: {replacements_made}")
        print(f"URLs procesadas para descarga: {len(urls)}")
        print(f"Archivos descargados exitosamente: {successful_downloads}")
        print(f"Archivos que fallaron: {failed_downloads}")
        print(f"Archivos omitidos (extensiones invalidas): {skipped_files}")
    except Exception as e:
        error_message = f"Error inesperado en la fase de descarga de archivos: {str(e)}"
        print(f"Error: {error_message}")
    finally:
        # Limpiar el archivo binario descargado
        if os.path.exists(workshop_binary_path):
            try:
                os.remove(workshop_binary_path)
            except OSError as e:
                print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")

        print("Comenzando pareo frontales con traseras")
        
        face_urls = []
        back_urls = []
        face_seen = set()
        back_seen = set()
        for pattern, url in unique_urls:
            if pattern == 'FaceURL' and url not in face_seen:
                if 'cloud-3.steamusercontent.com' in url.lower():
                    url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                else:
                    url_modificada = url
                face_urls.append(url_modificada)
                face_seen.add(url_modificada)
            elif pattern == 'BackURL' and url not in back_seen:
                if 'cloud-3.steamusercontent.com' in url.lower():
                    url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                else:
                    url_modificada = url
                back_urls.append(url_modificada)
                back_seen.add(url_modificada)
        
        print(f"Se descargarán {len(face_urls)} delanteras y {len(back_urls)} traseras")
        
        downloaded_urls_bin = set()
        successful_face_downloads = 0
        successful_back_downloads = 0
        failed_face_downloads = 0
        failed_back_downloads = 0
        
        for idx in range(max(len(face_urls), len(back_urls))):
            # Frontal
            if idx < len(face_urls):
                url = face_urls[idx]
                if url not in downloaded_urls_bin:
                    nombre = f"{idx+1}_a"
                    try:
                        response = verify_and_fetch_url(url)
                        content = b''.join(response.iter_content(chunk_size=8192))
                        ext = mimetypes.guess_extension(response.headers.get('content-type','').split(';')[0]) or ''
                        file_path = os.path.join(download_path, f"{nombre}{ext}")
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        print(f"Guardado Frontal: {file_path}")
                        downloaded_urls_bin.add(url)
                        successful_face_downloads += 1
                    except Exception as e:
                        print(f"Error al descargar {nombre} desde {url}: {e}")
                        failed_face_downloads += 1
                    time.sleep(1)  # Retraso para evitar saturar el servidor
            # Trasera
            if idx < len(back_urls):
                url = back_urls[idx]
                if url not in downloaded_urls_bin:
                    nombre = f"{idx+1}_b"
                    try:
                        response = verify_and_fetch_url(url)
                        content = b''.join(response.iter_content(chunk_size=8192))
                        ext = mimetypes.guess_extension(response.headers.get('content-type','').split(';')[0]) or ''
                        file_path = os.path.join(download_path, f"{nombre}{ext}")
                        with open(file_path, 'wb') as f:
                            f.write(content)
                        print(f"Guardado Trasera: {file_path}")
                        downloaded_urls_bin.add(url)
                        successful_back_downloads += 1
                    except Exception as e:
                        print(f"Error al descargar {nombre} desde {url}: {e}")
                        failed_back_downloads += 1
                    time.sleep(1)  # Retraso para evitar saturar el servidor
        
        # Resumen de descargas de FaceURL y BackURL
        print("\n=== Resumen de Pareo de Cartas ===")
        print(f"Se parearon exitosamente {successful_face_downloads} frontales con {successful_back_downloads} traseras")
        if failed_face_downloads > 0:
            print(f"Fallaron en la descarga {failed_face_downloads} frontales")
        if failed_back_downloads > 0: 
            print(f"Fallaron en la descarga {failed_back_downloads} traseras")
        
        if successful_downloads > 0:
            print(f"Archivo TXT de URLs reemplazadas: {output_txt_path}")
            print(f"Archivo CSV de URLs reemplazadas: {output_csv2_path}")

        # Eliminar duplicados de la lista general de descarga
        urls_no_duplicadas = []
        url_set_general = set()
        for pattern, url in unique_urls:
            if url not in url_set_general:
                urls_no_duplicadas.append((pattern, url_modificada))
                url_set_general.add(url_modificada)

if __name__ == "__main__":
    main()