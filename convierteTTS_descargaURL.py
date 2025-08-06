# Script para descargar un mod de Tabletop Simulator usando su URL de la Workshop.
# Extrae el ID de la URL, descarga el archivo principal usando una API externa, extrae URLs de archivos
# (imágenes, modelos 3D, pdf.) de ese archivo, utilizando los patrones especificados correspondientes 
# a los campos de datos.
# Reemplaza las URLs antiguas por unas válidas y descarga todos los archivos
# en un directorio automáticamente con el nombre del mod o designado por el usuario si ya existe.
# Maneja errores como URLs inválidas, permisos de escritura.
# Evita descargas duplicadas y valida extensiones de archivo mediante firmas de cabecera y tipos MIME.
# Simula un navegador para servicio de alojamiento de imagenes y reintenta cuando la descarga falla.
# Guarda automaticamente las URLs reemplazadas en un archivo TXT en caso de requerirlo a posterior.
# Verifica si la biblioteca 'requests' está instalada, mostrando un mensaje de instalación si falta.

# Creditos: Telegram @hinakawa y @alemarfar

try:
    import requests
except ImportError:
    print("Error: El módulo 'requests' no está instalado. Instálelo con 'pip install requests'.")
    exit(1)

import re
import os
import csv
import json
import mimetypes
import time
from urllib.parse import urlparse
from datetime import datetime

# Función para extraer el ID de una URL de Steam Community
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

# Reemplaza URLs específicas en una lista de URLs y guarda el resultado en un CSV temporal
def replace_urls_in_csv(urls, output_filename, download_path):
    archivo_salida_csv = os.path.join(download_path, output_filename)
    
    if not os.access(download_path, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {download_path}"
        print(error_message)
        return None, 0
    
    try:
        if not urls:
            error_message = "La lista de URLs está vacía."
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
                escritor_csv.writerow(["Mensaje", "No se encontraron URLs válidas o todas eran duplicadas"])
        
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
    retries = 3
    delay = 5  # segundos
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    for i in range(retries):
        try:
            response = requests.get(url, stream=True, allow_redirects=True, timeout=10, headers=headers)
            if response.status_code == 200:
                return response
            elif response.status_code == 429:
                if i == retries - 1:
                    raise requests.exceptions.RequestException(f"Código HTTP {response.status_code}")
                
                print(f"Aviso: Demasiadas peticiones al servidor. Esperando {delay} segundos antes de reintentar...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                error_message = f"Código HTTP {response.status_code}"
                raise requests.exceptions.RequestException(error_message)
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                error_message = f"Error final al verificar URL {url} tras {retries} intentos: {str(e)}"
                raise e
            print(f"Error en intento {i+1}/{retries} para URL {url}: {str(e)}. Reintentando en {delay} segundos...")
            time.sleep(delay)

    raise requests.exceptions.RequestException(f"No se pudo obtener la URL {url} después de {retries} intentos.")

# Determina la extensión de un archivo basado en el tipo MIME de los encabezados
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

# Verifica la firma de cabecera de un archivo para determinar su tipo y extensión
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
            error_message = f"URL inválida (no comienza con http:// o https://): {url}"
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
                    error_message = f"Extensión .bin no permitida para {pattern}, firma no es imagen: {url}"
                    print(error_message)
                    return False, error_message, False
                url_extension = signature_extension
            elif detected_mime_type not in ['image/jpeg', 'image/png']:
                error_message = f"Firma no válida para {pattern}: {detected_mime_type or 'desconocido'}: {url}"
                print(error_message)
                return False, error_message, False
        
        if pattern:
            if pattern == 'MeshURL':
                if detected_mime_type != 'model/obj' and content_type not in ['model/obj', 'text/plain', 'application/octet-stream']:
                    error_message = f"Firma o tipo MIME no válido para MeshURL: {detected_mime_type or content_type}: {url}"
                    print(error_message)
                    return False, error_message, False
                filename = f"{pattern}_{index}.obj"
            elif pattern == 'PDFUrl':
                if detected_mime_type != 'application/pdf' and content_type not in ['application/pdf']:
                    error_message = f"Firma o tipo MIME no válido para PDFUrl: {detected_mime_type or content_type}: {url}"
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
                error_message = f"Sin extensión válida detectada: {url}"
                print("Omitiendo archivo")
                return False, error_message, True
            elif new_extension == '.bin' and not signature_extension:
                error_message = f"Archivo sería nombrado como .bin: {url}"
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
                    error_message = f"No se pudo determinar la extensión del archivo: {url}"
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
    
    # Modo debug desactivado por defecto
    debug_mode = False

    # --- INICIO: LÓGICA PARA DESCARGAR DESDE URL ---
    workshop_url = input("Ingrese la URL del Workshop de Steam: ").strip()
    workshop_id = extract_steam_id(workshop_url)
    if not workshop_id:
        print("Error: No se pudo extraer un ID válido de la URL proporcionada.")
        return

    # Construir URL de la API y obtener información
    api_url = f"https://www.steamworkshopdownloader.cc/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
    
    try:
        print(f"Obteniendo información para el ID: {workshop_id}...")
        response = requests.get(api_url, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        workshop_title = data.get("title", "WorkshopItem")
        download_url = data.get("download_url")

        if not download_url:
            print("Error: No se pudo obtener la URL de descarga desde la API.")
            return

        # Crear un nombre de directorio válido a partir del título del workshop
        safe_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', data.get("title", "WorkshopItem_Archivos"))
        download_path = os.path.join(os.getcwd(), safe_folder_name)
        workshop_binary_path = os.path.join(download_path, f"{workshop_id}")

        # Verificar si el directorio o el archivo binario ya existen
        while os.path.exists(download_path) or os.path.exists(workshop_binary_path):
            if os.path.exists(download_path):
                print(f"El directorio propuesto '{download_path}' ya existe.")
            if os.path.exists(workshop_binary_path):
                print(f"El archivo '{workshop_binary_path}' ya existe en el directorio de descarga.")
            new_folder_name = input("Ingrese un nuevo nombre para el directorio de descarga: ").strip()
            new_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', new_folder_name)
            if not new_folder_name:
                new_folder_name = f"WorkshopItem_Archivos_{workshop_id}"
            download_path = os.path.join(os.getcwd(), new_folder_name)
            workshop_binary_path = os.path.join(download_path, f"{workshop_id}")
            print(f"El directorio propuesto es: {download_path}")
        
        # Evitar que el directorio de descarga se llame igual que el archivo de entrada
        input_file_base_name = workshop_id
        directory_name = os.path.basename(os.path.normpath(download_path)).lower()
        if directory_name == input_file_base_name.lower():
            new_download_path = os.path.join(os.path.dirname(download_path) or '.', f"{input_file_base_name}_dir")
            counter = 1
            while os.path.exists(new_download_path):
                new_download_path = os.path.join(os.path.dirname(download_path) or '.', f"{input_file_base_name}_dir_{counter}")
                counter += 1
            download_path = new_download_path
            workshop_binary_path = os.path.join(download_path, f"{workshop_id}")
            print(f"Advertencia: El directorio de descarga tiene el mismo nombre que el ID. Se cambió a: {download_path}")
        
        print(f"Los archivos se guardarán en: {download_path}")
        
        # Crear el directorio de descarga antes de descargar el archivo
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

        print(f"Descargando archivo principal de '{workshop_title}'...")
        workshop_response = requests.get(download_url, timeout=60)
        workshop_response.raise_for_status()

        with open(workshop_binary_path, 'wb') as f:
            f.write(workshop_response.content)

    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API o descargar el archivo principal: {e}")
        return
    except json.JSONDecodeError:
        print("Error: La respuesta de la API no es un JSON válido.")
        return
    # --- FIN: LÓGICA PARA DESCARGAR DESDE URL ---

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
            (r'ImageURL\x00.*?(http[^\x00]+)\x00', 'ImageURL'),
            (r'FaceURL\x00.*?(http[^\x00]+)\x00', 'FaceURL'),
            (r'BackURL\x00.*?(http[^\x00]+)\x00', 'BackURL'),
            (r'MeshURL\x00.*?(http[^\x00]+)\x00', 'MeshURL'),
            (r'DiffuseURL\x00.*?(http[^\x00]+)\x00', 'DiffuseURL'),
            (r'AssetbundleURL\x00.*?(http[^\x00]+)\x00', 'AssetbundleURL'),
            (r'AssetbundleSecondaryURL\x00.*?(http[^\x00]+)\x00', 'AssetbundleSecondaryURL'),
            (r'ImageSecondaryURL\x00.*?(http[^\x00]+)\x00', 'ImageSecondaryURL'),
            (r'PDFUrl\x00.*?(http[^\x00]+)\x00', 'PDFUrl')
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
            error_message = "No se encontraron URLs válidas"
            print(error_message)
            if os.path.exists(workshop_binary_path):
                try:
                    os.remove(workshop_binary_path)
                except OSError as e:
                    print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
            return
        
        print(f"Se extrajeron {converted_urls_count} URLs únicas.")

    except FileNotFoundError:
        error_message = f"El archivo {workshop_binary_path} no se encuentra."
        print(f"Error: {error_message}")
        if os.path.exists(workshop_binary_path):
            try:
                os.remove(workshop_binary_path)
            except OSError as e:
                print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
        return
    
    output_csv2 = f"{input_file_base_name}_replaced.csv"
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
            error_message = "El archivo CSV con URLs para descargar está vacío."
            print(error_message)
            if os.path.exists(workshop_binary_path):
                try:
                    os.remove(workshop_binary_path)
                except OSError as e:
                    print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
            return
        
        # Crear archivo TXT con solo las URLs
        output_txt = f"{input_file_base_name}_replaced.txt"
        output_txt_path = os.path.join(download_path, output_txt)
        try:
            with open(output_csv2_path, 'r', encoding='utf-8-sig') as csv_file:
                reader_csv = csv.reader(csv_file)
                urls_for_txt = [row[1] for row in reader_csv if len(row) >= 2 and row[1]]
            with open(output_txt_path, 'w', encoding='utf-8', newline='') as txt_file:
                if urls_for_txt:
                    txt_file.write('\n'.join(urls_for_txt))
                else:
                    txt_file.write("No se encontraron URLs válidas en el CSV")
        except Exception as e:
            error_message = f"Error al generar el archivo TXT {output_txt_path}: {str(e)}"
            print(f"Error: {error_message}")
        
        successful_downloads = 0
        failed_downloads = 0
        skipped_files = 0
        
        for index, row in enumerate(urls, start=1):
            if len(row) < 2:
                error_message = f"Fila inválida en el CSV (menos de 2 columnas): {row}"
                print(error_message)
                continue
            pattern, url = row[0], row[1]
            if not url:
                error_message = f"URL vacía para el patrón {pattern}"
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
        
        print("\n=== Resumen Final ===")
        print(f"Workshop ID procesado: {workshop_id}")
        print(f"Nombre Mod TTS: {workshop_title}")
        print(f"URLs extraídas: {converted_urls_count}")
        print(f"Reemplazos realizados: {replacements_made}")
        print(f"URLs procesadas para descarga: {len(urls)}")
        print(f"Archivos descargados exitosamente: {successful_downloads}")
        print(f"Archivos que fallaron: {failed_downloads}")
        print(f"Archivos omitidos: {skipped_files}")
        print(f"Archivo TXT de URLs reemplazadas generado: {output_txt_path}")
            
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
        # Limpiar el archivo CSV reemplazado
        if os.path.exists(output_csv2_path):
            try:
                os.remove(output_csv2_path)
            except OSError as e:
                print(f"No se pudo eliminar el archivo CSV '{output_csv2_path}': {e}")

if __name__ == "__main__":
    main()