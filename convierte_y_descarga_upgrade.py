# Script para descargar un mod de Tabletop Simulator usando su ID de la Workshop.
# Primero, descarga el archivo principal (.bin) usando una API externa.
# Luego, extrae todas las URLs de los assets (imágenes, modelos 3D, etc.) de ese archivo, 
# usando los campos de datos del archivo .bin  
# Reemplaza las URLs antiguas por unas válidas y descarga todos los assets 
# en un directorio con el mismo nombre del mod o uno designado por el usuario.
# Creditos: Telegram @hinakawa y @alemarfar
# Todas las funciones y los pasos estan comentados para mayor entendimiento

import re
import os
import json
import mimetypes
import requests
import logging
from urllib.parse import urlparse
from datetime import datetime

# Configuración del logging
def setup_logging(input_file, download_path, debug_mode=False):
    log_file = os.path.join(download_path, f"{input_file}_log.txt")
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG if debug_mode else logging.ERROR,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S'
    )
    if debug_mode:
        logging.debug(f"Modo debug activado. Log guardado en: {log_file}")
    return log_file

# Limpia una URL eliminando espacios en blanco
def clean_url(url):
    try:
        return url.strip()
    except Exception as e:
        logging.error(f"Error al limpiar URL {url}: {str(e)}")
        return None

# Extrae URLs de un archivo binario de Tabletop Simulator
def extract_urls_from_tts_binary(input_file, download_path, debug_mode=False):
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
                        # Reemplazar URLs de Steam directamente aquí
                        if 'cloud-3.steamusercontent.com' in cleaned_url.lower():
                            cleaned_url = cleaned_url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                        urls.append((url_type, cleaned_url))
                        if debug_mode:
                            logging.debug(f"URL válida encontrada: {url_type} - {cleaned_url}")
                elif cleaned_url:
                    logging.error(f"URL inválida omitida: {cleaned_url}")
        
        unique_urls = list(dict.fromkeys(urls))
        converted_urls_count = len(unique_urls)

        if unique_urls:
            print(f"Extracción completada: {input_file} ({converted_urls_count} URLs únicas)")
            if debug_mode:
                logging.debug(f"Se extrajeron {converted_urls_count} URLs únicas")
        else:
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

# Verifica la accesibilidad de una URL y obtiene su contenido
def verify_and_fetch_url(url):
    try:
        response = requests.get(url, stream=True, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return response
        else:
            error_message = f"Código HTTP {response.status_code}"
            logging.error(f"Error al verificar URL {url}: {error_message}")
            raise requests.exceptions.RequestException(error_message)
    except requests.exceptions.RequestException as e:
        error_message = f"Error al verificar URL {url}: {str(e)}"
        logging.error(error_message)
        raise e

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
def download_file(url, download_path, index, pattern, debug_mode=False):
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
                    new_file_path = os.path.join(download_path, new_filename)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{name}_{counter}{new_extension}"
                        new_file_path = os.path.join(download_path, new_filename)
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
    print("=== Tabletop Simulator URL Descargador ===")
    
    debug_input = input("¿Desea activar el modo debug, guardar log de errores? (si/no): ").strip().lower()
    debug_mode = debug_input in ['si', 's']
    if debug_mode:
        print("Modo debug activado. Se generarán logs detallados.")

    # Descarga desde Workshop con el ID de TTS 
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
        # Crear variable sin espacios para el directorio y el nombre del archivo
        workshop_title_no_spaces = ''.join(workshop_title.split())
        workshop_binary_path = f"{workshop_title_no_spaces}.bin"
        
        download_url = data.get("download_url")

        if not download_url:
            print("Error: No se pudo obtener la URL de descarga desde la API.")
            logging.error("No se encontró 'download_url' en la respuesta de la API.")
            return

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
    
    download_path_input = input(f"Ingrese el directorio donde se guardarán los archivos descargados (presione Enter para usar '{workshop_title_no_spaces}'): ").strip()
    
    # Usar el título del workshop sin espacios como directorio predeterminado si no se especifica otro
    download_path = download_path_input if download_path_input else workshop_title_no_spaces
    
    # Verificar que el directorio de descarga no tenga extensión .bin
    if download_path.lower().endswith('.bin'):
        download_path = os.path.splitext(download_path)[0]
        print(f"Advertencia: El directorio de descarga terminaba en '.bin'. Se eliminó la extensión: {download_path}")
        if debug_mode:
            logging.debug(f"Extensión .bin eliminada del directorio de descarga: {download_path}")
    
    try:
        os.makedirs(download_path, exist_ok=True)
        if debug_mode:
            logging.debug(f"Directorio de descarga creado o verificado: {download_path}")
    except OSError as e:
        error_message = f"No se pudo crear el directorio {download_path}: {str(e)}"
        print(f"Error: {error_message}")
        return
    
    if not os.access(download_path, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {download_path}"
        print(error_message)
        return
    
    log_file = setup_logging(workshop_id, download_path, debug_mode)
    if debug_mode:
        print(f"Registro de errores se guardará en: {log_file}")
    
    # Extraer URLs directamente y reemplazar las de Steam
    unique_urls, converted_urls_count = extract_urls_from_tts_binary(workshop_binary_path, download_path, debug_mode)
    
    if not unique_urls:
        error_message = "Error en la extracción de URLs. Proceso terminado."
        logging.error(error_message)
        print(error_message)
        # Limpieza del archivo binario descargado
        if os.path.exists(workshop_binary_path):
            try:
                os.remove(workshop_binary_path)
                print(f"Archivo temporal '{workshop_binary_path}' eliminado.")
            except OSError as e:
                print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")
        return
    
    print(f"Se extrajeron {converted_urls_count} URLs únicas.")
    
    successful_downloads = 0
    failed_downloads = 0
    skipped_files = 0
    
    for index, (pattern, url) in enumerate(unique_urls, start=1):
        if not url:
            error_message = f"URL vacía para el patrón {pattern}"
            logging.error(error_message)
            print(error_message)
            continue
        
        success, result, skipped = download_file(url, download_path, index, pattern, debug_mode)
        
        if success:
            successful_downloads += 1
            print(f"Descargado ({successful_downloads}/{len(unique_urls)}): {result}")
        elif skipped:
            skipped_files += 1
        else:
            failed_downloads += 1
    
    print("\n=== Resumen Final ===")
    print(f"Workshop ID procesado: {workshop_id} ('{workshop_title}')")
    print(f"URLs extraídas: {converted_urls_count}")
    print(f"Archivos descargados exitosamente: {successful_downloads}")
    print(f"Archivos que fallaron: {failed_downloads}")
    print(f"Archivos omitidos: {skipped_files}")
    if debug_mode:
        print(f"Errores registrados en: {log_file}")
        logging.debug(f"Resumen: {converted_urls_count} URLs extraídas, {successful_downloads} descargas exitosas, {failed_downloads} fallidas, {skipped_files} omitidas")
    
    # Limpiar el archivo binario descargado
    if os.path.exists(workshop_binary_path):
        try:
            os.remove(workshop_binary_path)
            print(f"Archivo temporal '{workshop_binary_path}' eliminado.")
        except OSError as e:
            print(f"No se pudo eliminar el archivo temporal '{workshop_binary_path}': {e}")

if __name__ == "__main__":
    main()