# Script para descargar un mod de Tabletop Simulator usando su ID de la Workshop.
# Primero, descarga el archivo principal (.bin) usando una API externa.
# Luego, extrae todas las URLs de los archivos (imágenes, modelos 3D, pdf) de ese archivo,
# utilizando los patrones especificados correspondientes a los campos de datos.
# Reemplaza las URLs antiguas por unas válidas y descarga todos los archivos
# en un directorio automáticamente con el nombre del mod o designado por el usuario si ya existe.
# Maneja errores como URLs inválidas, permisos de escritura, fallos de red, etc.
# Evita descargas duplicadas y valida extensiones de archivo mediante firmas de cabecera y tipos MIME.
# Posee modo debug para almacenar archivos intermedios (CSV y log) y log de errores detallados.
# Verifica si la biblioteca 'requests' está instalada, mostrando un mensaje de instalación si falta.

# Creditos: Telegram @hinakawa y @alemarfar

# Todas las funciones y los pasos están comentados para mayor entendimiento

# Verificación de la biblioteca requests
try:
    import requests
except ImportError:
    print("Error: La biblioteca 'requests' no está instalada.")
    print("Por favor, instálala ejecutando el siguiente comando en tu terminal:")
    print("pip install requests")
    exit(1)

import re
import os
import csv
import json
import mimetypes
import requests
import logging
import time
from urllib.parse import urlparse
from datetime import datetime

# Configuración del logging
def setup_logging(input_file, download_dir, debug_mode=False):
    log_file = None
    if debug_mode:
        log_file = os.path.join(download_dir, f"{input_file}_log.txt")
        logging.basicConfig(
            filename=log_file,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S'
        )
        logging.debug(f"Modo debug activado. Log guardado en: {log_file}")
    else:
        # Configurar logging para mostrar errores en consola
        logging.basicConfig(
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%d-%m-%Y %H:%M:%S',
            handlers=[logging.StreamHandler()]
        )
    return log_file

# Limpia una URL eliminando espacios en blanco
def clean_url(url):
    try:
        return url.strip()
    except Exception as e:
        logging.error(f"Error al limpiar URL {url}: {str(e)}")
        return None

# Extrae URLs de un archivo binario de Tabletop Simulator
def extract_urls_from_tts_binary(input_file, download_dir, debug_mode=False):
    if debug_mode:
        logging.debug(f"Iniciando extracción de URLs desde {input_file}")
    try:
        if not os.path.isfile(input_file):
            error_message = f"El archivo {input_file} no se encuentra."
            logging.error(error_message)
            print(f"Error: {error_message}")
            raise FileNotFoundError(error_message)
        
        with open(input_file, 'rb') as file:
            content = file.read()
        
        try:
            text = content.decode('utf-8', errors='ignore')
            if debug_mode:
                logging.debug(f"Contenido del archivo {input_file} decodificado correctamente")
        except UnicodeDecodeError as e:
            error_message = f"Error al decodificar el archivo binario {input_file}: {str(e)}"
            logging.error(error_message)
            print(f"Error: {error_message}")
            raise
        
        # Eliminar texto relacionado con Lua (funciones y bloques de código)
        lua_patterns = [
            r'function\s+[^\x00]*?end',  # Bloques function ... end
            r'\bfunction\b.*?\bend\b',   # Bloques function ... end (otra variante)
            r'\bif\b.*?\bthen\b.*?\bend\b',  # Bloques if ... then ... end
            r'\bwhile\b.*?\bend\b',      # Bloques while ... end
            r'\bfor\b.*?\bend\b',        # Bloques for ... end
            r'--\[\[.*?\]\]',            # Comentarios multilínea de Lua
            r'--.*?\n',                  # Comentarios de una línea
            r'\b(local|return|break|nil|true|false|and|or|not)\b'  # Palabras clave de Lua
        ]
        for pattern in lua_patterns:
            text = re.sub(pattern, '', text, flags=re.DOTALL | re.MULTILINE)
            if debug_mode:
                logging.debug(f"Patrón Lua eliminado: {pattern}")
        
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
                        if debug_mode:
                            logging.debug(f"URL válida encontrada: {url_type} - {cleaned_url}")
                elif cleaned_url:
                    logging.error(f"URL inválida omitida: {cleaned_url}")
        
        unique_urls = list(dict.fromkeys(urls))
        converted_urls_count = len(unique_urls)

        if not unique_urls:
            error_message = "No se encontraron URLs válidas"
            logging.error(error_message)
            print(error_message)
        
        return unique_urls, converted_urls_count

    except FileNotFoundError:
        return None, 0
    except Exception as e:
        error_message = f"Error inesperado en extracción de URLs: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, 0

# Reemplaza URLs específicas y guarda el resultado en un CSV solo si debug_mode=True
def replace_urls_in_csv(urls, output_filename, download_dir, debug_mode=False):
    if not os.access(download_dir, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {download_dir}"
        logging.error(error_message)
        print(error_message)
        return None, 0, []
    
    try:
        if not urls:
            error_message = "No hay URLs para procesar."
            logging.error(error_message)
            print(error_message)
            return None, 0, []
        
        if debug_mode:
            logging.debug(f"Procesando {len(urls)} URLs para reemplazo")
        
        seen_urls = set()
        replaced_rows = []
        
        for i, (pattern, url) in enumerate(urls, start=1):
            if 'cloud-3.steamusercontent.com' in url.lower():
                modified_url = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
            else:
                modified_url = url
            
            if modified_url not in seen_urls:
                seen_urls.add(modified_url)
                replaced_rows.append([pattern, modified_url])
        
        # Solo guardar el CSV si debug_mode es True
        output_csv_file = None
        if debug_mode:
            output_csv_file = os.path.join(download_dir, output_filename)
            with open(output_csv_file, 'w', encoding='utf-8-sig', newline='') as output_file:
                csv_writer = csv.writer(output_file)
                if replaced_rows:
                    csv_writer.writerows(replaced_rows)
                else:
                    csv_writer.writerow(["Mensaje", "No se encontraron URLs válidas o todas eran duplicadas"])
        
        print("\nResumen de procesamiento:")
        print(f"Filas procesadas: {len(urls)}")
        print(f"Reemplazos realizados: {len(replaced_rows)}")
        
        return output_csv_file, len(replaced_rows), replaced_rows

    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, 0, []

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
                logging.warning(f"Código HTTP 429 (Too Many Requests) para URL {url}. Reintentando en {delay} segundos...")
                print(f"Aviso: Demasiadas peticiones al servidor. Esperando {delay} segundos antes de reintentar...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                error_message = f"Código HTTP {response.status_code}"
                logging.error(f"Error al verificar URL {url}: {error_message}")
                raise requests.exceptions.RequestException(error_message)
        except requests.exceptions.RequestException as e:
            if i == retries - 1:
                error_message = f"Error final al verificar URL {url} tras {retries} intentos: {str(e)}"
                logging.error(error_message)
                raise e
            logging.warning(f"Error en intento {i+1}/{retries} para URL {url}: {str(e)}. Reintentando en {delay} segundos...")
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
        error_message = f"Error al verificar firma de cabecera: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, None

# Descarga un archivo desde una URL y lo guarda en el directorio especificado
def download_file(url, download_dir, index, pattern, debug_mode=False):
    if debug_mode:
        logging.debug(f"Iniciando descarga de URL: {url} (patrón: {pattern})")
    try:
        if not url.startswith(('http://', 'https://')):
            error_message = f"URL inválida (no comienza con http:// o https://): {url}"
            logging.error(error_message)
            print(error_message)
            return False, error_message, False
        
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        name, url_extension = os.path.splitext(os.path.basename(parsed_url.path))
        
        try:
            response = verify_and_fetch_url(url)
            if debug_mode:
                logging.debug(f"URL verificada exitosamente: {url}")
        except requests.exceptions.RequestException as e:
            return False, str(e), False
        
        content = b''
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content += chunk
                if len(content) >= 1024:
                    break
        
        content_type = response.headers.get('content-type', '').lower().split(';')[0]
        if debug_mode:
            logging.debug(f"Tipo MIME detectado: {content_type}")
        
        detected_mime_type, signature_extension = verify_header_signature(content, pattern)
        if debug_mode:
            logging.debug(f"Firma de cabecera: {detected_mime_type}, extensión: {signature_extension}")
        
        if pattern in ['FaceURL', 'BackURL']:
            if url_extension.lower() == '.bin':
                if detected_mime_type not in ['image/jpeg', 'image/png']:
                    error_message = f"Extensión .bin no permitida para {pattern}, firma no es imagen: {url}"
                    logging.error(error_message)
                    print(error_message)
                    return False, error_message, False
                url_extension = signature_extension
            elif detected_mime_type not in ['image/jpeg', 'image/png']:
                error_message = f"Firma no válida para {pattern}: {detected_mime_type or 'desconocido'}: {url}"
                logging.error(error_message)
                print(error_message)
                return False, error_message, False
        
        if pattern:
            if pattern == 'MeshURL':
                if detected_mime_type != 'model/obj' and content_type not in ['model/obj', 'text/plain', 'application/octet-stream']:
                    error_message = f"Firma o tipo MIME no válido para MeshURL: {detected_mime_type or content_type}: {url}"
                    logging.error(error_message)
                    print(error_message)
                    return False, error_message, False
                filename = f"{pattern}_{index}.obj"
            elif pattern == 'PDFUrl':
                if detected_mime_type != 'application/pdf' and content_type != 'application/pdf':
                    error_message = f"Firma o tipo MIME no válido para PDFUrl: {detected_mime_type or content_type}: {url}"
                    logging.error(error_message)
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
                logging.error(error_message)
                print("Omitiendo archivo")
                return False, error_message, True
            elif new_extension == '.bin' and not signature_extension:
                error_message = f"Archivo sería nombrado como .bin: {url}"
                logging.error(error_message)
                print("Omitiendo archivo")
                return False, error_message, True
        
        file_path = os.path.join(download_dir, filename)
        counter = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            name = name.rsplit('_', 1)[0]
            filename = f"{name}_{index}_{counter}{ext}"
            file_path = os.path.join(download_dir, filename)
            counter += 1
        
        with open(file_path, 'wb') as f:
            f.write(content)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        if debug_mode:
            logging.debug(f"Archivo descargado: {file_path}")
        
        if pattern not in ['MeshURL', 'PDFUrl', 'FaceURL', 'BackURL']:
            name, url_extension = os.path.splitext(os.path.basename(parsed_url.path))
            if not url_extension or url_extension.lower() not in [ext.lower() for ext in MIME_TO_EXTENSION.values()]:
                name, ext = os.path.splitext(filename)
                new_extension = get_file_extension(file_path, response.headers)
                if not new_extension and not signature_extension:
                    os.remove(file_path)
                    error_message = f"No se pudo determinar la extensión del archivo: {url}"
                    logging.error(error_message)
                    print("Omitiendo archivo")
                    return False, error_message, True
                if new_extension and not signature_extension and new_extension != '.bin':
                    new_filename = f"{name}{new_extension}"
                    new_file_path = os.path.join(download_dir, new_filename)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{name}_{counter}{new_extension}"
                        new_file_path = os.path.join(download_dir, new_filename)
                        counter += 1
                    try:
                        os.rename(file_path, new_file_path)
                        if debug_mode:
                            logging.debug(f"Archivo renombrado de {file_path} a {new_file_path}")
                    except OSError as e:
                        error_message = f"Error al renombrar archivo de {file_path} a {new_file_path}: {str(e)}"
                        logging.error(error_message)
                        print(error_message)
                        os.remove(file_path)
                        return False, error_message, True
                    file_path = new_file_path
                    filename = new_filename
        
        return True, filename, False
            
    except Exception as e:
        error_message = f"Error al descargar {url}: {str(e)}"
        logging.error(error_message)
        print(error_message)
        return False, error_message, False

# Punto de entrada principal del script
def main():
    print("=== Tabletop Simulator URL Downloader ===")
    
    debug_input = input("¿Desea activar el modo debug, guardar archivos CSV y log de errores? (si/no): ").strip().lower()
    debug_mode = debug_input in ['si', 's']
    if debug_mode:
        print("Modo debug activado. Se almacenarán los archivos CSV y se generarán logs detallados.")

    # --- INICIO: LÓGICA PARA DESCARGAR DESDE WORKSHOP ID ---
    workshop_id = input("Ingrese el ID del Workshop de Steam: ").strip()
    if not workshop_id.isdigit():
        print("Error: El ID del workshop debe ser un número.")
        return

    # Construir URL de la API y obtener información
    api_url = f"https://www.steamworkshopdownloader.cc/json?url=https://steamcommunity.com/sharedfiles/filedetails/?id={workshop_id}"
    
    try:
        print(f"Obteniendo información para el ID: {workshop_id}...")
        response = requests.get(api_url, timeout=15)
        response.raise_for_status() # Lanza un error si la petición falla (e.g. 404, 500)
        data = response.json()
        
        workshop_title = data.get("title", "WorkshopItem")
        download_url = data.get("download_url")

        if not download_url:
            print("Error: No se pudo obtener la URL de descarga desde la API.")
            logging.error("No se encontró 'download_url' en la respuesta de la API.")
            return

        # Crear un nombre de directorio válido a partir del título del workshop
        safe_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', data.get("title", "WorkshopItem_Files"))
        download_dir = os.path.join(os.getcwd(), safe_folder_name)

        # Verificar si el directorio ya existe
        while os.path.exists(download_dir):
            print(f"El directorio '{download_dir}' ya existe.")
            new_folder_name = input("Ingrese un nuevo nombre para el directorio de descarga: ").strip()
            new_folder_name = re.sub(r'[<>:"/\\|?*\s]', '_', new_folder_name)
            if new_folder_name.lower().endswith('.bin'):
                new_folder_name = new_folder_name[:-4]
            if not new_folder_name:
                new_folder_name = f"WorkshopItem_Files_{workshop_id}"
            download_dir = os.path.join(os.getcwd(), new_folder_name)
        
        print(f"Los archivos se guardarán en: {download_dir}")
        
        # Evitar que el directorio de descarga se llame igual que el archivo de entrada
        input_file_base_name = workshop_id
        directory_name = os.path.basename(os.path.normpath(download_dir)).lower()
        if directory_name == input_file_base_name.lower():
            new_download_dir = os.path.join(os.path.dirname(download_dir) or '.', f"{input_file_base_name}_dir")
            counter = 1
            while os.path.exists(new_download_dir):
                new_download_dir = os.path.join(os.path.dirname(download_dir) or '.', f"{input_file_base_name}_dir_{counter}")
                counter += 1
            download_dir = new_download_dir
            print(f"Advertencia: El directorio de descarga tiene el mismo nombre que el ID. Se cambió a: {download_dir}")
            if debug_mode:
                logging.debug(f"Directorio renombrado a: {download_dir}")
        
        # Crear el directorio de descarga antes de descargar el archivo .bin
        try:
            os.makedirs(download_dir, exist_ok=True)
            if debug_mode:
                logging.debug(f"Directorio de descarga creado o verificado: {download_dir}")
        except OSError as e:
            error_message = f"No se pudo crear el directorio {download_dir}: {str(e)}"
            print(f"Error: {error_message}")
            return

        # Verificar permisos de escritura en el directorio
        if not os.access(download_dir, os.W_OK):
            error_message = f"No se tienen permisos de escritura en el directorio {download_dir}"
            print(error_message)
            logging.error(error_message)
            return

        # Definir la ruta del archivo binario en el directorio de descarga
        workshop_binary_path = os.path.join(download_dir, f"{workshop_id}.bin")

        print(f"Descargando archivo principal de '{workshop_title}'...")
        workshop_response = requests.get(download_url, timeout=60)
        workshop_response.raise_for_status()

        with open(workshop_binary_path, 'wb') as f:
            f.write(workshop_response.content)
        
        print(f"Archivo principal '{workshop_binary_path}' descargado correctamente.")

    except requests.exceptions.RequestException as e:
        print(f"Error al contactar la API o descargar el archivo principal: {e}")
        logging.error(f"Error de red para ID {workshop_id}: {e}")
        return
    except json.JSONDecodeError:
        print("Error: La respuesta de la API no es un JSON válido.")
        logging.error("Error al decodificar JSON de la API.")
        return
    # --- FIN: LÓGICA PARA DESCARGAR DESDE WORKSHOP ID ---

    log_file = setup_logging(input_file_base_name, download_dir, debug_mode)
    
    unique_urls, converted_urls_count = extract_urls_from_tts_binary(workshop_binary_path, download_dir, debug_mode)
    
    if not unique_urls:
        error_message = "Error en la extracción de URLs. Proceso terminado."
        logging.error(error_message)
        print(error_message)
        # Limpieza del archivo binario descargado
        if os.path.exists(workshop_binary_path) and not debug_mode:
            os.remove(workshop_binary_path)
            logging.info(f"Archivo temporal '{workshop_binary_path}' eliminado.")
        elif debug_mode:
            logging.info(f"Archivo temporal '{workshop_binary_path}' conservado en {download_dir} por modo debug.")
        return
    
    print(f"Se extrajeron {converted_urls_count} URLs únicas.")
    
    output_csv = f"{input_file_base_name}_replaced.csv"
    output_csv_path, replacements_made, replaced_rows = replace_urls_in_csv(unique_urls, output_csv, download_dir, debug_mode)
    
    if not replaced_rows:
        error_message = "Error en el reemplazo de URLs. Proceso terminado."
        logging.error(error_message)
        print(error_message)
        if os.path.exists(workshop_binary_path) and not debug_mode:
            os.remove(workshop_binary_path)
            logging.info(f"Archivo temporal '{workshop_binary_path}' eliminado.")
        elif debug_mode:
            logging.info(f"Archivo temporal '{workshop_binary_path}' conservado en {download_dir} por modo debug.")
        return
    
    try:
        # Usar replaced_rows directamente en lugar de leer el CSV
        urls = replaced_rows
        
        if not urls:
            error_message = "No hay URLs válidas para descargar."
            logging.error(error_message)
            print(error_message)
            if os.path.exists(workshop_binary_path) and not debug_mode:
                os.remove(workshop_binary_path)
                logging.info(f"Archivo temporal '{workshop_binary_path}' eliminado.")
            elif debug_mode:
                logging.info(f"Archivo temporal '{workshop_binary_path}' conservado en {download_dir} por modo debug.")
            return
        
        successful_downloads = 0
        failed_downloads = 0
        skipped_files = 0
        
        for index, row in enumerate(urls, start=1):
            if len(row) < 2:
                error_message = f"Fila inválida en URLs procesadas (menos de 2 columnas): {row}"
                logging.error(error_message)
                print(error_message)
                continue
            pattern, url = row[0], row[1]
            if not url:
                error_message = f"URL vacía para el patrón {pattern}"
                logging.error(error_message)
                print(error_message)
                continue
            success, result, skipped = download_file(url, download_dir, index, pattern, debug_mode)
            
            if success:
                successful_downloads += 1
                print(f"Descargado ({successful_downloads}/{len(urls)}): {result}")
            elif skipped:
                skipped_files += 1
            else:
                failed_downloads += 1
            
            time.sleep(1) # Pausa de 1 segundo para no saturar el servidor
        
        print("\n=== Resumen Final ===")
        print(f"Workshop ID procesado: {workshop_id} ('{workshop_title}')")
        print(f"URLs extraídas: {converted_urls_count}")
        print(f"Reemplazos realizados: {replacements_made}")
        print(f"URLs procesadas para descarga: {len(urls)}")
        print(f"Archivos descargados exitosamente: {successful_downloads}")
        print(f"Archivos que fallaron: {failed_downloads}")
        print(f"Archivos omitidos: {skipped_files}")
        if debug_mode and output_csv_path:
            print(f"URLs reemplazadas guardadas en: {output_csv_path}")
        if debug_mode and log_file:
            print(f"Registro de errores se guardará en: {log_file}")
        if debug_mode:
            if os.path.exists(workshop_binary_path):
                print(f"Archivo binario guardado en: {workshop_binary_path}")
            
    except Exception as e:
        error_message = f"Error inesperado en la fase de descarga de archivos: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
    finally:
        # Limpieza del archivo binario descargado solo si no está en modo debug
        if os.path.exists(workshop_binary_path):
            if not debug_mode:
                try:
                    os.remove(workshop_binary_path)
                    logging.info(f"Archivo temporal '{workshop_binary_path}' eliminado.")
                except OSError as e:
                    error_message = f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}"
                    print(error_message)
                    logging.error(error_message)
            else:
                logging.info(f"Archivo temporal '{workshop_binary_path}' conservado en {download_dir} por modo debug.")

if __name__ == "__main__":
    main()
