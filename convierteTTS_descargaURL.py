# ... (importaciones y definiciones previas sin cambios)

def extraer_urls_desde_tts_binario(archivo_entrada, archivo_salida, ruta_archivo_log, modo_depuracion=False):
    try:
        if not os.path.isfile(archivo_entrada):
            mensaje_error = f"El archivo {archivo_entrada} no se encuentra."
            print(f"Error: {mensaje_error}")
            registrar_error(ruta_archivo_log, mensaje_error)
            raise FileNotFoundError(mensaje_error)
        
        if not archivo_salida.lower().endswith('.csv'):
            archivo_salida += '.csv'
        
        os.makedirs(os.path.dirname(archivo_salida) or '.', exist_ok=True)
        
        with open(archivo_entrada, 'rb') as archivo:
            contenido = archivo.read()
        
        try:
            texto = contenido.decode('utf-8', errors='ignore')
        except UnicodeDecodeError as e:
            mensaje_error = f"Error al decodificar el archivo binario {archivo_entrada}: {str(e)}"
            print(f"Error: {mensaje_error}")
            registrar_error(ruta_archivo_log, mensaje_error)
            raise
        
        patrones_url = [
            # ... (patrones sin cambios)
        ]

        urls_vistas = set()
        urls = []
        for patron, tipo_url in patrones_url:
            coincidencias = re.finditer(patron, texto, re.DOTALL)
            for coincidencia in coincidencias:
                url = coincidencia.group(1).strip()
                url_limpia = limpiar_url(url, ruta_archivo_log)
                if (url_limpia and 
                    (url_limpia.startswith('http://') or url_limpia.startswith('https://')) and 
                    '.' in url_limpia and 
                    not any(palabra in url_limpia.lower() for palabra in ['function', 'end', 'if', 'then', 'else', 'lua'])):
                    if url_limpia not in urls_vistas:
                        urls_vistas.add(url_limpia)
                        urls.append((tipo_url, url_limpia))
        
        urls_unicas = list(dict.fromkeys(urls))
        urls_convertidas = len(urls_unicas)

        if urls_unicas and modo_depuracion:
            with open(archivo_salida, 'w', encoding='utf-8-sig', newline='') as archivo:
                escritor = csv.writer(archivo)
                for tipo_url, url in urls_unicas:
                    escritor.writerow([tipo_url, url])
                if modo_depuracion:
                    print(f"Extracción completada: {archivo_entrada} TTS -> {archivo_salida} (CSV con {urls_convertidas} URLs únicas)")
                    print(f"Se convirtieron {urls_convertidas} URLs únicas.")
        elif not urls_unicas:
            print("No se encontraron URLs válidas.")
        
        return urls_unicas, archivo_salida if urls_unicas and modo_depuracion else None, urls_convertidas

    except FileNotFoundError:
        return None, None, 0
    except PermissionError as e:
        mensaje_error = f"No se tienen permisos para acceder o crear {archivo_salida}: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return None, None, 0
    except Exception as e:
        mensaje_error = f"Error inesperado en extracción de URLs: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return None, None, 0

def descargar_archivo(url, ruta_descarga, indice, patron, ruta_archivo_log, urls_descargadas, archivo_entrada, modo_depuracion=False):
    try:
        url_parseada = urlparse(url)
        nombre_archivo = os.path.basename(url_parseada.path)
        nombre, ext_url = os.path.splitext(os.path.basename(url_parseada.path))
        
        if ext_url.lower() == '.bin':
            print(f"Omitiendo archivo .bin: {url}")
            registrar_error(ruta_archivo_log, f"URL con extensión .bin detectada, no se descargará: {url}")
            return False, "Extensión .bin detectada", True
        
        if patron:
            if patron == 'MeshURL':
                nombre_archivo = f"{patron}_{indice}.obj"
            else:
                nombre_archivo = f"{patron}_{indice}"
        else:
            if not nombre_archivo or len(nombre_archivo) > 100:
                nombre_archivo = f'archivo_descargado_{indice}'
            else:
                nombre, ext = os.path.splitext(nombre_archivo)
                if not ext:
                    nombre_archivo = f"{nombre}_{indice}"
                else:
                    nombre_archivo = f"{nombre}_{indice}{ext}"
        
        try:
            respuesta = verificar_url(url)
            if respuesta.status_code != 200:
                mensaje_error = f"Error al descargar desde {url}: Código HTTP {respuesta.status_code}"
                print(f"Error al descargar {url}: Código HTTP {respuesta.status_code}")
                registrar_error(ruta_archivo_log, mensaje_error)
                return False, mensaje_error, False
        except requests.exceptions.RequestException as e:
            mensaje_error = f"Error al descargar desde {url}: {str(e)}"
            print(f"Error al descargar {url}: {str(e)}")
            registrar_error(ruta_archivo_log, mensaje_error)
            return False, mensaje_error, False
        
        if ext_url and ext_url != '.bin' and ext_url.lower() in [ext.lower() for ext in MIME_A_EXTENSION.values()]:
            nombre_archivo = f"{nombre}_{indice}{ext_url}"
        else:
            if patron == 'MeshURL':
                nombre_archivo = f"{patron}_{indice}.obj"
        
        ruta_archivo = os.path.join(ruta_descarga, nombre_archivo)
        contador = 1
        while os.path.exists(ruta_archivo):
            nombre, ext = os.path.splitext(nombre_archivo)
            nombre = nombre.rsplit('_', 1)[0]
            nombre_archivo = f"{nombre}_{indice}_{contador}{ext}"
            ruta_archivo = os.path.join(ruta_descarga, nombre_archivo)
            contador += 1
        
        with open(ruta_archivo, 'wb') as f:
            for chunk in respuesta.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
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
                    mensaje_error = f"Error al renombrar archivo de {ruta_archivo} a {nueva_ruta_archivo}: {str(e)}"
                    print(f"Error al descargar {url}: {str(e)}")
                    registrar_error(ruta_archivo_log, mensaje_error)
                    os.remove(ruta_archivo)
                    return False, mensaje_error, False
                ruta_archivo = nueva_ruta_archivo
                nombre_archivo = nuevo_nombre_archivo
        
        if url not in urls_descargadas and modo_depuracion:
            urls_descargadas.add(url)
            with open(os.path.join(ruta_descarga, f"{os.path.splitext(os.path.basename(archivo_entrada))[0]}_descargar.txt"), 'a', encoding='utf-8') as archivo_url:
                archivo_url.write(f"{url}\n")
            with open(os.path.join(ruta_descarga, f"{os.path.splitext(os.path.basename(archivo_entrada))[0]}_descargadas.txt"), 'a', encoding='utf-8') as archivo_url:
                archivo_url.write(f"{url}\n")
        
        print(f"Descargado: {nombre_archivo}")
        return True, None, False
            
    except Exception as e:
        mensaje_error = f"Error al descargar desde {url}: {str(e)}"
        print(f"Error al descargar {url}: {str(e)}")
        registrar_error(ruta_archivo_log, mensaje_error)
        return False, mensaje_error, False

def principal():
    archivo_entrada = input("Ingrese el nombre del archivo WorkshopUpload (sin extensión): ").strip()
    nombre_base = os.path.splitext(archivo_entrada)[0]
    ruta_descarga = input("Ingrese el directorio donde se guardarán los archivos descargados: ").strip()
    if not os.path.exists(ruta_descarga):
        os.makedirs(ruta_descarga)
    
    modo_depuracion = input("¿Desea activar el modo depuración? (Activa mensajes en pantalla, logs de error y guarda automáticamente los archivos CSV y TXT) (s/n): ").strip().lower() == 's'
    if modo_depuracion:
        print("Modo depuración activado. Los mensajes se mostrarán, el log de error y los archivos CSV y TXT se guardarán automáticamente.")
    else:
        print("Modo depuración desactivado. Los mensajes detallados no se mostrarán, no se guardará log de error ni archivos CSV y TXT.")
    
    if modo_depuracion and not os.access(ruta_descarga, os.W_OK):
        mensaje_error = f"No se tienen permisos de escritura en el directorio {ruta_descarga}"
        print(f"Error: {mensaje_error}")
        return
    
    ruta_archivo_log = os.path.join(ruta_descarga, f"{nombre_base}_log.txt")
    archivo_salida_csv = os.path.join(ruta_descarga, f"{nombre_base}_convertidas.csv")
    
    urls, csv_extraido, urls_convertidas = extraer_urls_desde_tts_binario(archivo_entrada, archivo_salida_csv, ruta_archivo_log, modo_depuracion)
    if not urls:
        print("Error en la extracción de URLs. Proceso terminado.")
        return
    
    try:
        archivo_reemplazado = os.path.join(ruta_descarga, f"{nombre_base}_reemplazadas.csv")
        reemplazos_realizados = 0
        descargas_invalidas = []
        archivos_bin_detectados = 0
        
        urls_reemplazadas_unicas = {}
        
        for patron, url in urls:
            if not url:
                mensaje_error = "URL vacía"
                registrar_error(ruta_archivo_log, f"Error en reemplazo, línea ignorada: {mensaje_error}")
                descargas_invalidas.append((patron, url, mensaje_error))
                continue
            if 'http://cloud-3.steamusercontent.com' in url:
                url_modificada = url.replace('http://cloud-3.steamusercontent.com', 'https://steamusercontent-a.akamaihd.net')
                reemplazos_realizados += 1
            else:
                url_modificada = url
            urls_reemplazadas_unicas[url_modificada] = patron
        
        if modo_depuracion:
            with open(archivo_reemplazado, 'w', encoding='utf-8', newline='') as archivo_csv_salida:
                escritor_csv = csv.writer(archivo_csv_salida)
                for url_modificada, patron in urls_reemplazadas_unicas.items():
                    escritor_csv.writerow([patron, url_modificada])
        
        ruta_archivo_urls = os.path.join(ruta_descarga, f"{nombre_base}_descargar.txt")
        if modo_depuracion:
            with open(ruta_archivo_urls, 'w', encoding='utf-8') as archivo_urls:
                for url_modificada in urls_reemplazadas_unicas:
                    archivo_urls.write(f"{url_modificada}\n")
        
        conteo_urls_reemplazadas_unicas = len(urls_reemplazadas_unicas)
        if modo_depuracion:
            print(f"Se generaron {conteo_urls_reemplazadas_unicas} URLs reemplazadas únicas.")
            print(f"Reemplazo completado. Se realizaron {reemplazos_realizados} reemplazos.")
            print(f"URLs reemplazadas guardadas en {archivo_reemplazado}")
            print(f"URLs reemplazadas guardadas en {ruta_archivo_urls}")
        
        urls_descargadas = set()
        descargas_exitosas = 0
        descargas_fallidas = 0
        descargas_invalidas = []
        
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
        
        print("\nResumen de conversión:")
        print(f"URLs convertidas: {urls_convertidas}")
        print(f"URLs reemplazadas: {conteo_urls_reemplazadas_unicas}")
        print("\nResumen de descarga:")
        print(f"URLs descargadas exitosamente: {descargas_exitosas}")
        print(f"URLs que fallaron: {descargas_fallidas}")
        print(f"Archivos con extensión .bin detectados (no descargados): {archivos_bin_detectados}")
        if modo_depuracion:
            print(f"Los errores se han almacenado en {ruta_archivo_log}")
            if os.path.exists(archivo_salida_csv):
                print(f"URLs extraídas guardadas en {archivo_salida_csv}")
            if os.path.exists(archivo_reemplazado):
                print(f"URLs reemplazadas guardadas en {archivo_reemplazado}")
            if os.path.exists(ruta_archivo_urls):
                print(f"Las URLs descargadas se han registrado en {ruta_archivo_urls}")
                
    except FileNotFoundError as e:
        mensaje_error = f"No se pudo encontrar el archivo {e.filename}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except PermissionError as e:
        mensaje_error = f"No se tienen permisos para leer/escribir los archivos: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except csv.Error as e:
        mensaje_error = f"Error al procesar el archivo CSV: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)
    except Exception as e:
        mensaje_error = f"Error inesperado: {str(e)}"
        print(f"Error: {mensaje_error}")
        registrar_error(ruta_archivo_log, mensaje_error)

if __name__ == "__main__":
    principal()
