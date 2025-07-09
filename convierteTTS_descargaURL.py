# Script para convertir el archivo binario de Tabletop Simulator obtenido desde https://steamworkshopdownloader.io/
# en un archivo de texto plano desde el cual se extrae segun los campos de datos las url y se almacenan en un archivo CSV
# al cual son reemplazadas las URLs por URLs validas para la descarga y se descargan usando el metodo GET en un 
# directorio designado por el usuario, tambien se almacenan los enlaces desde los cuales se descargo, posee un metodo 
# debug en el que guarda los errores, y se guardan los archivos CSV y TXT de los pasos intermedios. 
# Créditos: Telegram @hinakawa

# Todas las funciones y los pasos estan comentados para mayor entendimiento
import re
import os
import csv
import requests
from urllib.parse import urlparse
from datetime import datetime

# Diccionario que mapea tipos MIME a extensiones de archivo soportadas
MIME_A_EXTENSION = {
    'image/jpeg': '.jpg',
    'image/png': '.png',
    'application/pdf': '.pdf',
    'audio/mpeg': '.mp3',
    'audio/ogg': '.ogg',
    'model/obj': '.obj'
}

# Diccionario de firmas binarias para identificar tipos de archivo mediante cabeceras
FIRMAS_ARCHIVO = {
    b'\xFF\xD8\xFF': 'image/jpeg',  # Firma para archivos JPEG
    b'\x89\x50\x4E\x47\x0D\x0A\x1A\x0A': 'image/png',  # PNG
    b'\x25\x50\x44\x46': 'application/pdf',  # PDF
    b'\x4F\x67\x67\x53': 'audio/ogg',  # OGG audio
    b'\xFF\xFB': 'audio/mpeg',  # MP3 (MPEG-1 Layer III)
    b'\xFF\xFA': 'audio/mpeg',  # MP3 (MPEG-1 Layer III, alternate)
    b'v ': 'model/obj',  # OBJ (vertices)
    b'vn ': 'model/obj',  # OBJ (normales)
    b'f ': 'model/obj',  # OBJ (caras)
    b'mtllib ': 'model/obj'  # OBJ (referencia a materiales)
}

# Paso 2: Limpia una URL para asegurar que tenga un formato válido
def limpiar_url(url, ruta_archivo_log):
    """
    Valida y limpia una URL eliminando caracteres no deseados y verificando su formato.
    Registra errores en el archivo de log si la URL es inválida.
    """
    # Elimina espacios, comillas y etiquetas HTML de la URL
    url = url.strip().strip('"').strip("'")
    url = re.sub(r'<[^>]+>', '', url)
    # Verifica si la URL coincide con un formato válido (http o https)
    match = re.match(r'(https?://[\w\-\.:/?=&%]+)', url)
    if not match:
        # Registra un error si la URL no es válida
        registrar_error(ruta_archivo_log, f"URL inválida descartada: {url}")
        return None
    # Retorna la URL limpia y validada
    return match.group(1)

# Paso 3: Extrae URLs de un archivo binario TTS y las guarda en un CSV
def extraer_urls_desde_tts_binario(archivo_entrada, archivo_salida, ruta_archivo_log, modo_depuracion=False):
    """
    Lee un archivo binario TTS, extrae URLs basadas en patrones predefinidos,
    las valida y las guarda en un archivo CSV.
    """
    try:
        # Verifica si el archivo de entrada existe
        if not os.path.isfile(archivo_entrada):
            mensaje_error = f"El archivo {archivo_entrada} no se encuentra."
            print(f"Error: {mensaje_error}")
            registrar_error(ruta_archivo_log, mensaje_error)
            raise FileNotFoundError(mensaje_error)
        
        # Asegura que el archivo de salida tenga extensión .csv
        if not archivo_salida.lower().endswith('.csv'):
            archivo_salida += '.csv'
        
        # Crea el directorio de salida si no existe
        os.makedirs(os.path.dirname(archivo_salida) or '.', exist_ok=True)
        
        # Lee el contenido del archivo binario
        try:
            with open(archivo_entrada, 'rb') as archivo:
                contenido = archivo.read()
        except Exception as e:
            # Maneja errores al intentar leer el archivo binario, como permisos insuficientes o archivo corrupto
            mensaje_error = f"Error al leer el archivo binario {archivo_entrada}: {str(e)}"
            print(f"Error: {mensaje_error}")
            registrar_error(ruta_archivo_log, mensaje_error)
            raise
        
        # Decodifica el contenido binario a texto, ignorando errores
        try:
            texto = contenido.decode('utf-8', errors='ignore')
        except UnicodeDecodeError as e:
            # Maneja errores de decodificación si el archivo no es un texto UTF-8 válido
            mensaje_error = f"Error al decodificar el archivo binario {archivo_entrada}: {str(e)}"
            print(f"Error: {mensaje_error}")
            registrar_error(ruta_archivo_log, mensaje_error)
            raise
        
        # Define patrones para buscar URLs específicas en el archivo TTS
        patrones_url = [
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

        # Conjunto para evitar duplicados de URLs
        urls_vistas = set()
        urls = []
        # Busca URLs en el texto según los patrones definidos
        for patron, tipo_url in patrones_url:
            coincidencias = re.finditer(patron, texto, re.DOTALL)
            for coincidencia in coincidencias:
                url = coincidencia.group(1).strip()
                url_limpia = limpiar_url(url, ruta_archivo_log)
                # Valida la URL limpia y filtra URLs no deseadas
                if (url_limpia and 
                    (url_limpia.startswith('http://') or url_limpia.startswith('https://')) and 
                    '.' in url_limpia and 
                    not any(palabra in url_limpia.lower() for palabra in ['function', 'end', 'if', 'then', 'else', 'lua'])):
                    if url_limpia not in urls_vistas:
                        urls_vistas.add(url_limpia)
                        urls.append((tipo_url, url_limpia))
        
        # Elimina URLs duplicadas manteniendo el orden
        urls_unicas = list(dict.fromkeys(urls))
        urls_convertidas = len(urls_unicas)

        # Guarda las URLs en un archivo CSV si se encontraron
        if urls_unicas:
            with open(archivo_salida, 'w', encoding='utf-8-sig', newline='') as archivo:
                escritor = csv.writer(archivo)
                for tipo_url, url in urls_unicas:
                    escritor.writerow([tipo_url, url])
                if modo_depuracion:
                    print(f"Extracción completada: {archivo_entrada} TTS -> {archivo_salida} (CSV con {urls_convertidas} URLs únicas)")
                    print(f"Se convirtieron {urls_convertidas} URLs únicas.")
        else:
            print("No se encontraron URLs válidas.")
        
        # Retorna las URLs extraídas, el archivo CSV y el conteo
        return urls_unicas, archivo_salida, urls_convertidas

    except FileNotFoundError:
        # Maneja el caso en que el archivo de entrada no se encuentra
        # Retorna None para indicar fallo y evitar procesamiento adicional
        return None, None, 0
    except PermissionError as e:
        # Maneja errores de permisos al intentar crear o acceder al archivo de salida
        mensaje_error = f"No se tienen permisos para acceder o crear {archivo_salida}: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return None, None, 0
    except Exception as e:
        # Captura cualquier otro error inesperado durante la extracción de URLs
        mensaje_error = f"Error inesperado en extracción de URLs: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return None, None, 0

# Paso 4: Registra mensajes de error en un archivo de log con marca de tiempo
def registrar_error(ruta_archivo_log, mensaje):
    
    # Escribe mensajes de error en un archivo de log con una marca de tiempo.
    # Formatea la fecha y hora actual
    marca_tiempo = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    # Añade el mensaje de error al archivo de log
    with open(ruta_archivo_log, 'a', encoding='utf-8') as archivo_log:
        archivo_log.write(f"[{marca_tiempo}] {mensaje}\n")

# Paso 5: Verifica el tipo de archivo analizando las cabeceras binarias
def verificar_cabecera_archivo(ruta_archivo, ruta_archivo_log):
    """
    Analiza las cabeceras de un archivo para determinar su tipo MIME
    comparándolas con las firmas definidas.
    """
    try:
        # Lee los primeros 4096 bytes del archivo
        with open(ruta_archivo, 'rb') as f:
            cabecera = f.read(4096)
            # Compara la cabecera con las firmas conocidas
            for firma, tipo_mime in FIRMAS_ARCHIVO.items():
                if tipo_mime == 'model/obj':
                    if isinstance(firma, bytes) and firma in cabecera:
                        return tipo_mime
                else:
                    if isinstance(firma, bytes) and cabecera.startswith(firma[:min(len(firma), len(cabecera))]):
                        return tipo_mime
            # Retorna None si no se identifica el tipo
            return None
    except Exception as e:
        # Maneja errores al intentar leer el archivo o verificar la cabecera
        mensaje_error = f"Error al verificar la cabecera de {ruta_archivo}: {str(e)}"
        registrar_error(ruta_archivo_log, mensaje_error)
        return None

# Paso 6: Determina la extensión del archivo basada en su tipo MIME
def obtener_extension_archivo(ruta_archivo, cabeceras, ruta_archivo_log):
    """
    Obtiene la extensión adecuada para un archivo según su tipo MIME,
    verificado mediante las cabeceras.
    """
    # Verifica el tipo MIME del archivo
    mime_real = verificar_cabecera_archivo(ruta_archivo, ruta_archivo_log)
    # Retorna la extensión correspondiente si el tipo MIME es válido
    if mime_real and mime_real in MIME_A_EXTENSION:
        return MIME_A_EXTENSION[mime_real]
    return None

# Paso 7: Verifica la disponibilidad de una URL mediante una solicitud HTTP
def verificar_url(url):
    
    # Realiza una solicitud HTTP para verificar si una URL es accesible.
    # Envía una solicitud GET con soporte para redirecciones y un tiempo de espera
    return requests.get(url, stream=True, allow_redirects=True, timeout=30)

# Paso 8: Descarga un archivo desde una URL y lo guarda con la extensión adecuada
def descargar_archivo(url, ruta_descarga, indice, patron, ruta_archivo_log, urls_descargadas, archivo_entrada, modo_depuracion=False):
    """
    Descarga un archivo desde una URL, asigna un nombre único y verifica su extensión.
    Registra el proceso en archivos de texto y maneja errores.
    """
    try:
        # Parsea la URL para obtener el nombre del archivo
        url_parseada = urlparse(url)
        nombre_archivo = os.path.basename(url_parseada.path)
        nombre, ext_url = os.path.splitext(os.path.basename(url_parseada.path))
        
        # Omite archivos con extensión .bin
        if ext_url.lower() == '.bin':
            print(f"Omitiendo archivo .bin: {url}")
            registrar_error(ruta_archivo_log, f"URL con extensión .bin detectada, no se descargará: {url}")
            return False, "Extensión .bin detectada", True
        
        # Asigna un nombre basado en el patrón si está disponible
        if patron:
            if patron == 'MeshURL':
                nombre_archivo = f"{patron}_{indice}.obj"
            else:
                nombre_archivo = f"{patron}_{indice}"
        else:
            # Usa un nombre genérico si el nombre es inválido o demasiado largo
            if not nombre_archivo or len(nombre_archivo) > 100:
                nombre_archivo = f'archivo_descargado_{indice}'
            else:
                nombre, ext = os.path.splitext(nombre_archivo)
                if not ext:
                    nombre_archivo = f"{nombre}_{indice}"
                else:
                    nombre_archivo = f"{nombre}_{indice}{ext}"
        
        # Verifica la accesibilidad de la URL
        try:
            respuesta = verificar_url(url)
            if respuesta.status_code != 200:
                mensaje_error = f"Error al descargar desde {url}: Código HTTP {respuesta.status_code}"
                print(f"Error al descargar {url}: Código HTTP {respuesta.status_code}")
                registrar_error(ruta_archivo_log, mensaje_error)
                return False, mensaje_error, False
        except requests.exceptions.RequestException as e:
            # Maneja errores de red, como problemas de conexión o tiempos de espera
            mensaje_error = f"Error al descargar desde {url}: {str(e)}"
            print(f"Error al descargar {url}: {str(e)}")
            registrar_error(ruta_archivo_log, mensaje_error)
            return False, mensaje_error, False
        
        # Usa la extensión de la URL si es válida
        if ext_url and ext_url != '.bin' and ext_url.lower() in [ext.lower() for ext in MIME_A_EXTENSION.values()]:
            nombre_archivo = f"{nombre}_{indice}{ext_url}"
        else:
            if patron == 'MeshURL':
                nombre_archivo = f"{patron}_{indice}.obj"
        
        # Genera una ruta única para el archivo
        ruta_archivo = os.path.join(ruta_descarga, nombre_archivo)
        contador = 1
        while os.path.exists(ruta_archivo):
            nombre, ext = os.path.splitext(nombre_archivo)
            nombre = nombre.rsplit('_', 1)[0]
            nombre_archivo = f"{nombre}_{indice}_{contador}{ext}"
            ruta_archivo = os.path.join(ruta_descarga, nombre_archivo)
            contador += 1
        
        # Descarga y guarda el archivo
        with open(ruta_archivo, 'wb') as f:
            for chunk in respuesta.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        # Verifica la extensión si la URL no la proporciona
        nombre, ext_url = os.path.splitext(os.path.basename(url_parseada.path))
        if not ext_url or ext_url.lower() not in [ext.lower() for ext in MIME_A_EXTENSION.values()]:
            nombre, ext = os.path.splitext(nombre_archivo)
            nueva_ext = obtener_extension_archivo(ruta_archivo, respuesta.headers, ruta_archivo_log)
            if not nueva_ext:
                os.remove(ruta_archivo)
                mensaje_error = f"No se pudo determinar la extensión para {url}, archivo eliminado"
                print(f"Error al descargar {url}: {mensaje_error}")
                registrar_error(ruta_archivo_log, mensaje_error)
                return False, mensaje_error, False
            if nueva_ext:
                nuevo_nombre_archivo = f"{nombre}{nueva_ext}"
                nueva_ruta_archivo = os.path.join(ruta_descarga, nuevo_nombre_archivo)
                contador = 1
                while os.path.exists(nueva_ruta_archivo):
                    nuevo_nombre_archivo = f"{nombre}_{contador}{nueva_ext}"
                    nueva_ruta_archivo = os.path.join(ruta_descarga, nuevo_nombre_archivo)
                    contador += 1
                try:
                    os.rename(ruta_archivo, nueva_ruta_archivo)
                except OSError as e:
                    # Maneja errores al renombrar el archivo, como permisos insuficientes
                    mensaje_error = f"Error al renombrar archivo de {ruta_archivo} a {nueva_ruta_archivo}: {str(e)}"
                    print(f"Error al descargar {url}: {str(e)}")
                    registrar_error(ruta_archivo_log, mensaje_error)
                    os.remove(ruta_archivo)
                    return False, mensaje_error, False
                ruta_archivo = nueva_ruta_archivo
                nombre_archivo = nuevo_nombre_archivo
        
        # Registra la URL descargada en archivos de texto
        if url not in urls_descargadas:
            urls_descargadas.add(url)
            with open(os.path.join(ruta_descarga, f"{os.path.splitext(os.path.basename(archivo_entrada))[0]}_descargar.txt"), 'a', encoding='utf-8') as archivo_url:
                archivo_url.write(f"{url}\n")
            with open(os.path.join(ruta_descarga, f"{os.path.splitext(os.path.basename(archivo_entrada))[0]}_descargadas.txt"), 'a', encoding='utf-8') as archivo_url:
                archivo_url.write(f"{url}\n")
        
        print(f"Descargado: {nombre_archivo}")
        return True, None, False
            
    except Exception as e:
        # Captura cualquier error inesperado durante la descarga
        mensaje_error = f"Error al descargar desde {url}: {str(e)}"
        print(f"Error al descargar {url}: {str(e)}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return False, mensaje_error, False

# Paso 1: Coordina la ejecución del programa, solicitando entrada del usuario y gestionando el flujo
def principal():
    """
    Función principal que coordina el proceso de extracción y descarga de URLs.
    Solicita al usuario el archivo de entrada, el directorio de salida y el modo de depuración.
    """
    # Solicita el nombre del archivo de entrada
    archivo_entrada = input("Ingrese el nombre del archivo WorkshopUpload (sin extensión): ").strip()
    nombre_base = os.path.splitext(archivo_entrada)[0]
    # Solicita el directorio donde se guardarán los archivos
    ruta_descarga = input("Ingrese el directorio donde se guardarán los archivos descargados: ").strip()
    # Crea el directorio si no existe
    if not os.path.exists(ruta_descarga):
        os.makedirs(ruta_descarga)
    
    # Pregunta si se desea activar el modo de depuración
    modo_depuracion = input("¿Desea activar el modo depuración? (Activa mensajes en pantalla, logs de error y guarda automáticamente los archivos CSV) (s/n): ").strip().lower() == 's'
    if modo_depuracion:
        print("Modo depuración activado. Los mensajes se mostrarán, el log de error y los archivos CSV y TXT se guardarán automáticamente.")
    else:
        print("Modo depuración desactivado. Los mensajes detallados no se mostrarán, no se guardará log de error ni archivos CSV y TXT.")
    
    # Verifica permisos de escritura en el directorio si está en modo depuración
    if modo_depuracion and not os.access(ruta_descarga, os.W_OK):
        mensaje_error = f"No se tienen permisos de escritura en el directorio {ruta_descarga}"
        print(f"Error: {mensaje_error}")
        return
    
    # Define rutas para el archivo de log y el CSV de salida
    ruta_archivo_log = os.path.join(ruta_descarga, f"{nombre_base}_log.txt")
    archivo_salida_csv = os.path.join(ruta_descarga, f"{nombre_base}_convertidas.csv")
    
    # Extrae URLs del archivo binario
    urls, csv_extraido, urls_convertidas = extraer_urls_desde_tts_binario(archivo_entrada, archivo_salida_csv, ruta_archivo_log, modo_depuracion)
    if not urls:
        print("Error en la extracción de URLs. Proceso terminado.")
        return
    
    try:
        # Verifica si el archivo CSV extraído existe
        if not os.path.exists(csv_extraido):
            mensaje_error = f"El archivo {csv_extraido} no existe"
            print(f"Error: {mensaje_error}")
            return
        
        # Define la ruta para el CSV con URLs reemplazadas
        archivo_reemplazado = os.path.join(ruta_descarga, f"{nombre_base}_reemplazadas.csv")
        reemplazos_realizados = 0
        descargas_invalidas = []
        archivos_bin_detectados = 0
        
        # Diccionario para almacenar URLs únicas reemplazadas
        urls_reemplazadas_unicas = {}
        
        # Lee el CSV extraído y reemplaza URLs específicas
        with open(csv_extraido, 'r', encoding='utf-8') as archivo_csv:
            lector_csv = csv.reader(archivo_csv)
            for fila in lector_csv:
                if not fila or len(fila) < 2:
                    mensaje_error = "Formato incorrecto: menos de dos columnas"
                    registrar_error(ruta_archivo_log, f"Error en reemplazo, línea ignorada: {mensaje_error}")
                    descargas_invalidas.append(("", "", mensaje_error))
                    continue
                patron, url = fila[0], fila[1]
                if not url:
                    mensaje_error = "URL vacía"
                    registrar_error(ruta_archivo_log, f"Error en reemplazo, línea ignorada: {mensaje_error}")
                    descargas_invalidas.append((patron, url, mensaje_error))
                    continue
                # Reemplaza URLs de Steam por URL de Akamaihd
                if 'http://cloud-3.steamusercontent.com' in url:
                    url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                    reemplazos_realizados += 1
                else:
                    url_modificada = url
                urls_reemplazadas_unicas[url_modificada] = patron
        
        # Guarda las URLs reemplazadas en un nuevo CSV
        with open(archivo_reemplazado, 'w', encoding='utf-8', newline='') as archivo_csv_salida:
            escritor_csv = csv.writer(archivo_csv_salida)
            for url_modificada, patron in urls_reemplazadas_unicas.items():
                escritor_csv.writerow([patron, url_modificada])
        
        # Guarda las URLs reemplazadas en un archivo de texto
        ruta_archivo_urls = os.path.join(ruta_descarga, f"{nombre_base}_descargar.txt")
        with open(ruta_archivo_urls, 'w', encoding='utf-8') as archivo_urls:
            for url_modificada in urls_reemplazadas_unicas:
                archivo_urls.write(f"{url_modificada}\n")
        
        conteo_urls_reemplazadas_unicas = len(urls_reemplazadas_unicas)
        if modo_depuracion:
            print(f"Se generaron {conteo_urls_reemplazadas_unicas} URLs reemplazadas únicas.")
            print(f"Reemplazo completado. Se realizaron {reemplazos_realizados} reemplazos.")
            print(f"Los resultados se han guardado en {archivo_reemplazado}")
            print(f"URLs reemplazadas guardadas en {ruta_archivo_urls}")
        
        # Conjunto para rastrear URLs descargadas
        urls_descargadas = set()
        descargas_exitosas = 0
        descargas_fallidas = 0
        descargas_invalidas = []
        
        # Descarga cada URL reemplazada
        for indice, (url, patron) in enumerate(urls_reemplazadas_unicas.items(), start=1):
            if url:
                exito, razon, es_bin = descargar_archivo(url, ruta_descarga, indice, patron, ruta_archivo_log, urls_descargadas, archivo_entrada, modo_depuracion)
                if es_bin:
                    archivos_bin_detectados += 1
                elif exito:
                    descargas_exitosas += 1
                else:
                    descargas_fallidas += 1
                    descargas_invalidas.append((patron, url, razon))
            else:
                mensaje_error = f"URL vacía para el patrón {patron}"
                print(f"Error al descargar: {mensaje_error}")
                registrar_error(ruta_archivo_log, mensaje_error)
                descargas_invalidas.append((patron, url, mensaje_error))
                descargas_fallidas += 1
        
        # Imprime un resumen del proceso
        print("\nResumen de conversión:")
        print(f"URLs convertidas: {urls_convertidas}")
        print(f"URLs reemplazadas: {conteo_urls_reemplazadas_unicas}")
        print("\nResumen de descarga:")
        print(f"URLs descargadas exitosamente: {descargas_exitosas}")
        print(f"URLs que fallaron: {descargas_fallidas}")
        print(f"Archivos con extensión .bin detectados (no descargados): {archivos_bin_detectados}")
        if modo_depuracion:
            print(f"Los errores se han almacenado en {ruta_archivo_log}")
            print(f"Las URLs descargadas se han registrado en {ruta_archivo_urls}")
                
    except FileNotFoundError as e:
        # Maneja el caso en que el archivo CSV extraído no se encuentra
        mensaje_error = f"No se pudo encontrar el archivo {e.filename}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except PermissionError as e:
        # Maneja errores de permisos al intentar leer o escribir archivos
        mensaje_error = f"No se tienen permisos para leer/escribir los archivos: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except csv.Error as e:
        # Maneja errores al procesar el archivo CSV, como formato incorrecto
        mensaje_error = f"Error al procesar el archivo CSV: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except Exception as e:
        # Captura cualquier error inesperado en el procesamiento principal
        mensaje_error = f"Error inesperado: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)

if __name__ == "__main__":
    principal()
