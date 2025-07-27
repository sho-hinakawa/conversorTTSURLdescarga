# Script para convertir el archivo binario de Tabletop Simulator obtenido desde 
# https://steamworkshopdownloader.io/ en un archivo de texto plano desde el cual 
# se extrae segun los campos de datos las URLs y se almacenan en un archivo CSV
# al cual son reemplazadas las URLs por URLs validas para la descarga y se 
# descargan usando el metodo GET en un directorio designado por el usuario, 
# tambien se almacenan los enlaces desde los cuales se descargo, posee un metodo 
# debug en el que guarda los errores, y se guardan los archivos CSV y TXT de los 
# pasos intermedios. 
# Creditos: Telegram @hinakawa
# Todas las funciones y los pasos estan comentados para mayor entendimiento

import re
import os
import csv
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

# Extrae URLs de un archivo binario de Tabletop Simulator y las guarda en un CSV
def extract_urls_from_tts_binary(input_file, output_file, download_path, debug_mode=False):
    if debug_mode:
        logging.debug(f"Iniciando extracción de URLs desde {input_file}")
    try:
        if not os.path.isfile(input_file):
            error_message = f"El archivo {input_file} no se encuentra."
            logging.error(error_message)
            print(f"Error: {error_message}")
            raise FileNotFoundError(error_message)
        
        if not output_file.lower().endswith('.csv'):
            output_file += '.csv'
        
        output_file = os.path.join(download_path, output_file)
        
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
                        urls.append((url_type, cleaned_url))
                        if debug_mode:
                            logging.debug(f"URL válida encontrada: {url_type} - {cleaned_url}")
                elif cleaned_url:
                    logging.error(f"URL inválida omitida: {cleaned_url}")
        
        unique_urls = list(dict.fromkeys(urls))
        converted_urls_count = len(unique_urls)

        if unique_urls:
            with open(output_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                for url_type, url in unique_urls:
                    writer.writerow([url_type, url])
                print(f"Extracción completada: {input_file} -> {output_file} (CSV con {converted_urls_count} URLs únicas)")
                if debug_mode:
                    logging.debug(f"CSV generado: {output_file} con {converted_urls_count} URLs únicas")
        else:
            error_message = "No se encontraron URLs válidas"
            logging.error(error_message)
            print(error_message)
        
        return unique_urls, output_file, converted_urls_count

    except FileNotFoundError:
        return None, None, 0
    except Exception as e:
        error_message = f"Error inesperado en extracción de URLs: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, None, 0

# Reemplaza URLs específicas en un archivo CSV y guarda el resultado en un nuevo CSV
def replace_urls_in_csv(input_file, output_filename, download_path, debug_mode=False):
    # Obtener el directorio del archivo de entrada
    input_dir = os.path.dirname(input_file) or '.'
    archivo_salida_csv = os.path.join(input_dir, output_filename)
    
    # Verificar permisos de escritura en el directorio del archivo de entrada
    if not os.access(input_dir, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {input_dir}"
        logging.error(error_message)
        print(error_message)
        return None, 0
    
    try:
        # Leer el archivo CSV de entrada
        with open(input_file, 'r', encoding='utf-8-sig') as archivo_entrada:
            lector_csv = csv.reader(archivo_entrada)
            filas = list(lector_csv)
        
        if not filas:
            error_message = "El archivo CSV de entrada está vacío."
            logging.error(error_message)
            print(error_message)
            return None, 0
        
        if debug_mode:
            logging.debug(f"Se leyeron {len(filas)} filas del CSV {input_file}")
        
        # Procesar las filas, reemplazar URLs y eliminar duplicados
        urls_vistas = set()
        filas_reemplazadas = []
        
        for i, fila in enumerate(filas, start=1):
            if len(fila) < 2:
                logging.error(f"Fila inválida en el CSV (menos de 2 columnas): {fila}")
                continue
            
            patron, url = fila[0], fila[1]
            
            # Reemplazar la URL (insensible a mayúsculas/minúsculas)
            if 'cloud-3.steamusercontent.com' in url.lower():
                url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
            else:
                url_modificada = url
            
            # Añadir solo si la URL no ha sido vista
            if url_modificada not in urls_vistas:
                urls_vistas.add(url_modificada)
                filas_reemplazadas.append([patron, url_modificada])
        
        # Escribir el archivo CSV de salida
        with open(archivo_salida_csv, 'w', encoding='utf-8-sig', newline='') as archivo_salida:
            escritor_csv = csv.writer(archivo_salida)
            if filas_reemplazadas:
                escritor_csv.writerows(filas_reemplazadas)
            else:
                escritor_csv.writerow(["Mensaje", "No se encontraron URLs válidas o todas eran duplicadas"])
        
        # Imprimir resumen
        print("\nResumen de procesamiento:")
        print(f"Filas procesadas: {len(filas)}")
        print(f"Reemplazos realizados: {len(filas_reemplazadas)}")
        print(f"Archivo CSV de salida generado: {archivo_salida_csv}")
        
        return archivo_salida_csv, len(filas_reemplazadas)

    except FileNotFoundError as e:
        error_message = f"No se pudo encontrar el archivo {e.filename}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, 0
    except PermissionError as e:
        error_message = f"No se tienen permisos para leer/escribir los archivos: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, 0
    except csv.Error as e:
        error_message = f"Error al procesar el archivo CSV: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return None, 0
    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
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
    
    debug_input = input("¿Desea activar el modo debug, guardar archivos CSV y log de errores? (si/no): ").strip().lower()
    debug_mode = debug_input in ['si', 's']
    if debug_mode:
        print("Modo debug activado. Se almacenaran los archivos CSV y se generarán logs detallados.")
    
    input_file = input("Ingrese el nombre del archivo WorkshopUpload (sin extensión): ").strip()
    
    download_path = input("Ingrese el directorio donde se guardarán los archivos descargados: ").strip()
    
    input_file_lower = input_file.lower()
    directory_name = os.path.basename(os.path.normpath(download_path)).lower()
    if directory_name == input_file_lower:
        download_path = os.path.join(os.path.dirname(download_path) or '.', f"{os.path.basename(os.path.normpath(download_path))}_dir")
        print(f"Advertencia: El directorio de descarga tiene el mismo nombre que el archivo de entrada. Se cambió a: {download_path}")
        if debug_mode:
            logging.debug(f"Directorio renombrado a: {download_path}")
    
    try:
        os.makedirs(download_path, exist_ok=True)
        if debug_mode:
            logging.debug(f"Directorio de descarga creado o verificado: {download_path}")
    except OSError as e:
        error_message = f"No se pudo crear el directorio {download_path}: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
        return
    
    if not os.access(download_path, os.W_OK):
        error_message = f"No se tienen permisos de escritura en el directorio {download_path}"
        logging.error(error_message)
        print(error_message)
        return
    
    log_file = setup_logging(input_file, download_path, debug_mode)
    if debug_mode:
        print(f"Registro de errores se guardará en: {log_file}")
    
    output_csv1 = f"{input_file}_converted.csv"
    unique_urls, output_csv1, converted_urls_count = extract_urls_from_tts_binary(input_file, output_csv1, download_path, debug_mode)
    
    if not unique_urls:
        error_message = "Error en la extracción de URLs. Proceso terminado."
        logging.error(error_message)
        print(error_message)
        return
    
    print(f"Se extrajeron {converted_urls_count} URLs únicas.")
    
    output_csv2 = f"{input_file}_replaced.csv"
    output_csv2, replacements_made = replace_urls_in_csv(output_csv1, output_csv2, download_path, debug_mode)
    
    if not output_csv2:
        error_message = "Error en el reemplazo de URLs. Proceso terminado."
        logging.error(error_message)
        print(error_message)
        return
    
    print(f"Se realizaron {replacements_made} reemplazos de URLs.")
    
    try:
        with open(output_csv2, 'r', encoding='utf-8-sig') as input_file:
            reader_csv = csv.reader(input_file)
            urls = list(reader_csv)
        
        if not urls:
            error_message = "El archivo CSV está vacío."
            logging.error(error_message)
            print(error_message)
            return
        
        successful_downloads = 0
        failed_downloads = 0
        skipped_files = 0
        
        for index, row in enumerate(urls, start=1):
            if len(row) < 2:
                error_message = f"Fila inválida en el CSV (menos de 2 columnas): {row}"
                logging.error(error_message)
                print(error_message)
                continue
            pattern, url = row[0], row[1]
            if not url:
                error_message = f"URL vacía para el patrón {pattern}"
                logging.error(error_message)
                print(error_message)
                continue
            
            success, result, skipped = download_file(url, download_path, index, pattern, debug_mode)
            
            if success:
                successful_downloads += 1
                print(f"Descargado ({successful_downloads}): {result}")
            elif skipped:
                skipped_files += 1
            else:
                failed_downloads += 1
        
        print("\n=== Resumen Final ===")
        print(f"URLs extraídas: {converted_urls_count}")
        print(f"Reemplazos realizados: {replacements_made}")
        print(f"URLs procesadas para descarga: {len(urls)}")
        print(f"URLs descargadas exitosamente: {successful_downloads}")
        print(f"URLs que fallaron: {failed_downloads}")
        print(f"URLs omitidas: {skipped_files}")
        if debug_mode:
            print(f"Errores registrados en: {log_file}")
            logging.debug(f"Resumen: {converted_urls_count} URLs extraídas, {replacements_made} reemplazos, {successful_downloads} descargas exitosas, {failed_downloads} fallidas, {skipped_files} omitidas")
            
    except FileNotFoundError as e:
        error_message = f"No se pudo encontrar el archivo {e.filename}"
        logging.error(error_message)
        print(f"Error: {error_message}")
    except PermissionError as e:
        error_message = f"No se tienen permisos para leer/escribir los archivos: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
    except csv.Error as e:
        error_message = f"Error al procesar el archivo CSV: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")
    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
        logging.error(error_message)
        print(f"Error: {error_message}")

if __name__ == "__main__":
    main()
