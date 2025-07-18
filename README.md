# Conversor de archivos TTS WorkshopUpload en assets descargados desde el mismo archivo 

Este script en Python permite convertir un archivo WorkshopUpload de Tabletop Simulator desde https://steamworkshopdownloader.io/ en archivos que se descargan a un directorio especificado por el usuario.

**Creditos** Telegram @hinakawa

## Caracteristicas
- Lee desde un archivo binario de TTS del Workshop especificado por el usuario
- Realiza la conversion a archivo CSV obteniendo los campo de datos terminados en URL y su url
- Realiza reemplazo de las url del CSV anterior en un nuevo CSV con las URLs validas para descargar
- Verifica que sean URLs unicas
- Detecta extensiones de los archivos segun su cabecera descargada y le asiga el MIME Type correspondiente
  a los correspondientes a TTS
- Descarga las URLs indicando nombre del campo de datos utilizando el metodo HTTP GET a un directorio especificado por el usuario
- Identifica la extension del archivo identificando la cabecera leyendo los primeros 4096 bytes del archivo y comparandolos con archivos conocidos de TTS
- Posee metodo debug para entregar mensajes en pantalla, guardar errores y almacenar los archivos CSV y TXT de los pasos anteriores

## Requisitos
- **Python**: Versión 3.6 o superior.
- **Librería `requests`**:
```bash
 pip install requests
```
   

