# Script para convertir el archivo binario de Tabletop Simulator obtenido desde https://steamworkshopdownloader.io/
# en un archivo de texto plano desde el cual se extrae segun los campos de datos las url y se almacenan en un archivo CSV
# al cual son reemplazadas las URLs por URLs validas para la descarga y se descargan en un directorio designado por
# el usuario, tambien se almacenan los enlaces desde los cuales se descargo, posee un metodo debug en el que guarda
# los errores, y se guardan los archivos CSV y TXT de los pasos intermedios. 
# Créditos: Telegram @hinakawa

# Todos los pasos y funciones estan con sus comentarios respectivos
import re
import os
import csv
import requests #requiere instalar libreria, pip install request
from urllib.parse import urlparse
from datetime import datetime

# Diccionario para mapear tipos MIME a extensiones comunes
MIME_TO_EXTENSION = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'image/bmp': '.bmp',
    'image/webp': '.webp',
    'application/pdf': '.pdf',
    'audio/mpeg': '.mp3',
    'audio/ogg': '.ogg',
    'audio/wav': '.wav',
    'model/obj': '.obj',
    'model/stl': '.stl'
}

# Diccionario de firmas de archivo para verificar cabeceras
FILE_SIGNATURES = {
    b'\xFF\xD8\xFF': 'image/jpeg',  # JPEG
    b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': 'image/png',  # PNG
    b'\x42\x4D': 'image/bmp',  # BMP
    b'\x52\x49\x46\x46....\x57\x45\x42\x50': 'image/webp',  # WebP
    b'\x25\x50\x44\x46': 'application/pdf',  # PDF
    b'\x4F\x67\x67\x53': 'audio/ogg',  # OGG audio
    b'\x52\x49\x46\x46....\x57\x41\x56\x45': 'audio/wav',  # WAV
    b'v ': 'model/obj',  # OBJ (vertices)
    b'vn ': 'model/obj',  # OBJ (normales)
    b'f ': 'model/obj',  # OBJ (caras)
    b'mtllib ': 'model/obj',  # OBJ (referencia a materiales)
    b'solid ': 'model/stl'  # STL ASCII (comienza con "solid ")
}

# Paso 2: Limpiar URLs para asegurar formato valido
def clean_url(url, log_file_path):
    #Funcion: Limpia una URL eliminando comillas, etiquetas HTML y caracteres no validos, validando su formato.
    url = url.strip().strip('"').strip("'")
    url = re.sub(r'<[^>]+>', '', url)
    match = re.match(r'(https?://[\w\-\.:/?=&%]+)', url)
    if not match:
        log_error(log_file_path, f"URL invalida descartada: {url}")
        return None
    return match.group(1)

# Paso 3: Extraer URLs de archivo binario
def extract_urls_from_tts_binary(input_file, output_file, log_file_path, debug_mode=False):
    try:
        if not os.path.isfile(input_file):
            error_message = f"El archivo {input_file} no se encuentra."
            print(f"Error: {error_message}")
            log_error(log_file_path, error_message)
            raise FileNotFoundError(error_message)
        
        if not output_file.lower().endswith('.csv'):
            output_file += '.csv'
        
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)
        
        try:
            with open(input_file, 'rb') as file:
                content = file.read()
        except Exception as e:
            error_message = f"Error al leer el archivo binario {input_file}: {str(e)}"
            print(f"Error: {error_message}")
            log_error(log_file_path, error_message)
            raise
        
        try:
            text = content.decode('utf-8', errors='ignore')
        except UnicodeDecodeError as e:
            error_message = f"Error al decodificar el archivo binario {input_file}: {str(e)}"
            print(f"Error: {error_message}")
            log_error(log_file_path, error_message)
            raise
        
        url_patterns = [
            (r'TableURL\x00.*?(https?://[^\x00]*)\x00', 'TableURL'),
            (r'LutURL\x00.*?(https?://[^\x00]*)\x00', 'LutURL'),
            (r'FaceURL\x00.*?(https?://[^\x00]*)\x00', 'FaceURL'),
            (r'BackURL\x00.*?(https?://[^\x00]*)\x00', 'BackURL'),
            (r'MeshURL\x00.*?(https?://[^\x00]*)\x00', 'MeshURL'),
            (r'DiffuseURL\x00.*?(https?://[^\x00]*)\x00', 'DiffuseURL'),
            (r'NormalURL\x00.*?(https?://[^\x00]*)\x00', 'NormalURL'),
            (r'ColliderURL\x00.*?(https?://[^\x00]*)\x00', 'ColliderURL'),
            (r'PDFUrl\x00.*?(https?://[^\x00]*)\x00', 'PDFUrl'),
            (r'ImageURL\x00.*?(https?://[^\x00]*)\x00', 'ImageURL'),
            (r'ImageSecondaryURL\x00.*?(https?://[^\x00]*)\x00', 'ImageSecondaryURL'),
            (r'SkyURL\x00.*?(https?://[^\x00]*)\x00', 'SkyURL'),
            (r'BoardURL\x00.*?(https?://[^\x00]*)\x00', 'BoardURL'),
            (r'SoundURL\x00.*?(https?://[^\x00]*)\x00', 'SoundURL'),
            (r'CustomURL\x00.*?(https?://[^\x00]*)\x00', 'CustomURL'),
            (r'TextureURL\x00.*?(https?://[^\x00]*)\x00', 'TextureURL'),
            (r'SpecularURL\x00.*?(https?://[^\x00]*)\x00', 'SpecularURL'),
            (r'EmissiveURL\x00.*?(https?://[^\x00]*)\x00', 'EmissiveURL'),
            (r'HeightURL\x00.*?(https?://[^\x00]*)\x00', 'HeightURL'),
            (r'OcclusionURL\x00.*?(https?://[^\x00]*)\x00', 'OcclusionURL'),
            (r'CustomObjectURL\x00.*?(https?://[^\x00]*)\x00', 'CustomObjectURL'),
            (r'ExternalObjectURL\x00.*?(https?://[^\x00]*)\x00', 'ExternalObjectURL'),
            (r'RulesURL\x00.*?(https?://[^\x00]*)\x00', 'RulesURL'),
            (r'ReflectionURL\x00.*?(https?://[^\x00]*)\x00', 'ReflectionURL')
        ]

        seen_urls_only = set()
        urls = []
        for pattern, url_type in url_patterns:
            matches = re.finditer(pattern, text, re.DOTALL)
            for match in matches:
                url = match.group(1).strip()
                cleaned_url = clean_url(url, log_file_path)
                if (cleaned_url and 
                    (cleaned_url.startswith('http://') or cleaned_url.startswith('https://')) and 
                    '.' in cleaned_url and 
                    not any(keyword in cleaned_url.lower() for keyword in ['function', 'end', 'if', 'then', 'else', 'lua'])):
                    if cleaned_url not in seen_urls_only:
                        seen_urls_only.add(cleaned_url)
                        urls.append((url_type, cleaned_url))

        unique_urls = list(dict.fromkeys(urls))
        converted_urls = len(unique_urls)

        if unique_urls:
            with open(output_file, 'w', encoding='utf-8-sig', newline='') as file:
                writer = csv.writer(file)
                for url_type, url in unique_urls:
                    writer.writerow([url_type, url])
                print(f"Se convirtieron {converted_urls} URLs unicas.")
        else:
            print("No se encontraron URLs validas.")
        
        print(f"Extraccion completada: {input_file} TTS -> {output_file} (CSV con {converted_urls} URLs unicas)")
        return unique_urls, output_file, converted_urls

    except FileNotFoundError:
        return None, None, 0
    except PermissionError:
        error_message = f"No se tienen permisos para acceder o crear {output_file}"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)
        return None, None, 0
    except Exception as e:
        error_message = f"Error inesperado en extraccion de URLs: {str(e)}"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)
        return None, None, 0

# Paso 4: Registrar errores en archivo de log
def log_error(log_file_path, message):
    timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    with open(log_file_path, 'a', encoding='utf-8') as log_file:
        log_file.write(f"[{timestamp}] {message}\n")

# Paso 5: Verificar tipo de archivo mediante cabeceras
def check_file_header(file_path, log_file_path):
    try:
        with open(file_path, 'rb') as f:
            header = f.read(4096)
            for signature, mime_type in FILE_SIGNATURES.items():
                if mime_type == 'model/obj' or mime_type == 'model/stl':
                    if isinstance(signature, bytes) and signature in header:
                        return mime_type
                else:
                    if isinstance(signature, bytes) and header.startswith(signature[:min(len(signature), len(header))]):
                        return mime_type
            # Verificación específica para STL binario
            if len(header) >= 84:  # 80 bytes de cabecera + 4 bytes de número de triángulos
                try:
                    num_triangles = int.from_bytes(header[80:84], byteorder='little')
                    if num_triangles > 0:  # Número razonable de triángulos
                        return 'model/stl'
                except ValueError:
                    pass
            return None
    except Exception as e:
        error_message = f"Error al verificar la cabecera de {file_path}: {str(e)}"
        log_error(log_file_path, error_message)
        return None

# Paso 6: Determinar extension del archivo
def get_file_extension(file_path, headers, log_file_path):
    real_mime = check_file_header(file_path, log_file_path)
    if real_mime and real_mime in MIME_TO_EXTENSION:
        return MIME_TO_EXTENSION[real_mime]
    return None

# Paso 7: Descargar archivos desde URLs
def download_file(url, download_path, index, pattern, log_file_path, downloaded_urls, input_file, debug_mode=False):
    try:
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        name, url_ext = os.path.splitext(os.path.basename(parsed_url.path))
        
        # Verificar si la extensión es .bin
        if url_ext.lower() == '.bin':
            log_error(log_file_path, f"URL con extensión .bin detectada, no se descargará: {url}")
            return False, "Extensión .bin detectada", True  # Tercer valor indica que es .bin
        
        if pattern:
            filename = f"{pattern}_{index}"
        else:
            if not filename or len(filename) > 50:
                filename = f'archivo_descargado_{index}'
            else:
                name, ext = os.path.splitext(filename)
                if not ext:
                    filename = f"{name}_{index}"
                else:
                    filename = f"{name}_{index}{ext}"
        
        try:
            head_response = requests.head(url, allow_redirects=True)
            if head_response.status_code != 200:
                error_message = f"Error al descargar desde {url}: Codigo {head_response.status_code}"
                print(f"Error al descargar {url}")
                log_error(log_file_path, error_message)
                return False, error_message, False
        except Exception as e:
            error_message = f"Error al descargar desde {url}: {str(e)}"
            print(f"Error al descargar {url}")
            log_error(log_file_path, error_message)
            return False, error_message, False
        
        if url_ext and url_ext != '.bin' and url_ext in [ext for ext in MIME_TO_EXTENSION.values()]:
            filename = f"{name}_{index}{url_ext}"
        else:
            if pattern == 'MeshURL':
                ext = '.obj'
            else:
                ext = None
            filename = f"{name}_{index}{ext or ''}" if not pattern else f"{pattern}_{index}{ext or ''}"
        
        file_path = os.path.join(download_path, filename)
        counter = 1
        while os.path.exists(file_path):
            name, ext = os.path.splitext(filename)
            name = name.rsplit('_', 1)[0]
            filename = f"{name}_{index}_{counter}{ext}"
            file_path = os.path.join(download_path, filename)
            counter += 1
        
        response = requests.get(url, stream=True)
        
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            name, url_ext = os.path.splitext(os.path.basename(parsed_url.path))
            if not url_ext or url_ext not in [ext for ext in MIME_TO_EXTENSION.values()]:
                name, ext = os.path.splitext(filename)
                if ext in ['', '.obj', '.wav']:
                    if pattern == 'MeshURL':
                        new_ext = '.obj'
                    else:
                        new_ext = get_file_extension(file_path, response.headers, log_file_path)
                        if not new_ext:
                            os.remove(file_path)
                            error_message = f"No se pudo determinar la extensión para {url}, archivo eliminado"
                            print(f"Error al descargar {url}")
                            log_error(log_file_path, error_message)
                            return False, error_message, False
                    new_filename = f"{name}{new_ext}"
                    new_file_path = os.path.join(download_path, new_filename)
                    counter = 1
                    while os.path.exists(new_file_path):
                        new_filename = f"{name}_{counter}{new_ext}"
                        new_file_path = os.path.join(download_path, new_filename)
                        counter += 1
                    try:
                        os.rename(file_path, new_file_path)
                    except OSError as e:
                        error_message = f"Error al renombrar archivo de {file_path} a {new_file_path}: {str(e)}"
                        print(f"Error al descargar {url}")
                        log_error(log_file_path, error_message)
                        os.remove(file_path)
                        return False, error_message, False
                    file_path = new_file_path
                    filename = new_filename
            
            if url not in downloaded_urls:
                downloaded_urls.add(url)
                with open(os.path.join(download_path, f"{os.path.splitext(os.path.basename(input_file))[0]}_descargadas.txt"), 'a', encoding='utf-8') as url_file:
                    url_file.write(f"{url}\n")
            
            print(f"Descargado: {filename}")
            return True, None, False
        else:
            error_message = f"Error al descargar desde {url}: Codigo {response.status_code}"
            print(f"Error al descargar {url}")
            log_error(log_file_path, error_message)
            return False, error_message, False
            
    except Exception as e:
        error_message = f"Error al descargar desde {url}: {str(e)}"
        print(f"Error al descargar {url}")
        log_error(log_file_path, error_message)
        return False, error_message, False

# Paso 1: Coordinar ejecucion del programa
def main():
    input_file = input("Ingrese el nombre del archivo WorkshopUpload (sin extension): ").strip()
    base_name = os.path.splitext(input_file)[0]
    download_path = input("Ingrese el directorio donde se guardaran los archivos descargados: ").strip()
    if not os.path.exists(download_path):  # Corrected from downloadembry
        os.makedirs(download_path)
    
    debug_mode = input("Desea activar el modo debug? (Activa logs de error y guarda automaticamente los archivos CSV ) (s/n): ").strip().lower() == 's'
    if debug_mode:
        print("Modo debug activado. Los archivos CSV y log se guardaran automaticamente.")

    log_file_path = os.path.join(download_path, f"{base_name}_log.txt")
    output_file_csv = os.path.join(download_path, f"{base_name}_convertidas.csv")
    
    urls, extracted_csv, converted_urls = extract_urls_from_tts_binary(input_file, output_file_csv, log_file_path, debug_mode)
    if not urls:
        print("Error en la extraccion de URLs. Proceso terminado.")
        return
    
    try:
        if not os.path.exists(extracted_csv):
            error_message = f"El archivo {extracted_csv} no existe"
            print(f"Error: {error_message}")
            return
        
        output_file_replaced = os.path.join(download_path, f"{base_name}_reemplazadas.csv")
        replacements_made = 0
        invalid_downloads = []
        bin_files_detected = 0
        
        # Conjunto para rastrear URLs reemplazadas únicas
        unique_replaced_urls = {}
        
        # Leer archivo de URLs convertidas y realizar reemplazos
        with open(extracted_csv, 'r', encoding='utf-8') as csv_file:
            csv_reader = csv.reader(csv_file)
            for row in csv_reader:
                if not row or len(row) < 2:
                    error_message = "Formato incorrecto: menos de dos columnas"
                    log_error(log_file_path, f"Error en reemplazo, linea ignorada: {error_message}")
                    invalid_downloads.append(("", "", error_message))
                    continue
                patron, url = row[0], row[1]
                if not url:
                    error_message = "URL vacia"
                    log_error(log_file_path, f"Error en reemplazo, linea ignorada: {error_message}")
                    invalid_downloads.append((patron, url, error_message))
                    continue
                if 'http://cloud-3.steamusercontent.com' in url:
                    modified_url = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                    replacements_made += 1
                else:
                    modified_url = url
                # Almacenar la última ocurrencia de la URL reemplazada con su patrón asociado
                unique_replaced_urls[modified_url] = patron
        
        # Escribir URLs reemplazadas únicas al archivo
        with open(output_file_replaced, 'w', encoding='utf-8', newline='') as out_csv_file:
            csv_writer = csv.writer(out_csv_file)
            for modified_url, patron in unique_replaced_urls.items():
                csv_writer.writerow([patron, modified_url])
        
        unique_replaced_count = len(unique_replaced_urls)
        print(f"Reemplazo completado. Se realizaron {replacements_made} reemplazos.")
        print(f"Se generaron {unique_replaced_count} URLs reemplazadas únicas.")
        print(f"Los resultados se han guardado en {output_file_replaced}")
        
        # Inicializar archivo de URLs descargadas
        url_file_path = os.path.join(download_path, f"{base_name}_descargadas.txt")
        with open(url_file_path, 'w', encoding='utf-8') as url_file:
            url_file.write("")
        
        downloaded_urls = set()
        successful_downloads = 0
        failed_downloads = 0
        invalid_downloads = []
        
        # Descargar desde la lista de URLs reemplazadas únicas
        for index, (url, pattern) in enumerate(unique_replaced_urls.items(), start=1):
            if url:
                success, reason, is_bin = download_file(url, download_path, index, pattern, log_file_path, downloaded_urls, input_file, debug_mode)
                if is_bin:
                    bin_files_detected += 1
                elif success:
                    successful_downloads += 1
                else:
                    failed_downloads += 1
                    invalid_downloads.append((pattern, url, reason))
            else:
                error_message = f"URL vacia para el patrón {pattern}"
                print(f"Error al descargar")
                log_error(log_file_path, error_message)
                invalid_downloads.append((pattern, url, error_message))
                failed_downloads += 1
        
        print("\nResumen de conversión:")
        print(f"URLs convertidas: {converted_urls}")
        print(f"URLs reemplazadas: {unique_replaced_count}")
        print("\nResumen de descarga:")
        print(f"URLs descargadas exitosamente: {successful_downloads}")
        print(f"URLs que fallaron: {failed_downloads}")
        print(f"Archivos con extensión .bin detectados (no descargados): {bin_files_detected}")
        if debug_mode:
            print(f"Los errores se han almacenado en {log_file_path}")
            print(f"Las URLs descargadas se han registrado en {url_file_path}")
                
    except FileNotFoundError as e:
        error_message = f"No se pudo encontrar el archivo {e.filename}"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)
    except PermissionError:
        error_message = "No se tienen permisos para leer/escribir los archivos"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)
    except csv.Error as e:
        error_message = f"Error al procesar el archivo CSV: {str(e)}"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)
    except Exception as e:
        error_message = f"Error inesperado: {str(e)}"
        print(f"Error: {error_message}")
        log_error(log_file_path, error_message)

if __name__ == "__main__":
    main()
