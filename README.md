# Descargador de archivos de TTS desde la URL del Workshop 

Este script en Python permite descargan los archivos de un mod del Workshop de Tabletop Simulator dada la URL del Workshop un directorio dado por el nombre del mod

**Creditos** Telegram @Gandalf775 @hinakawa @alemarfar

## Caracteristicas
- Lee el ID desde el Workshop de TTS especificado por el usuario
- Realiza la conversion a archivo obteniendo los campo de datos terminados en URL y su url
- Realiza reemplazo de las url con las URLs validas para descargar
- Verifica que sean URLs unicas
- Detecta extensiones de los archivos segun su cabecera descargada y le asiga el MIME Type correspondiente
  a los correspondientes a TTS
- Descarga las URLs indicando nombre del campo de datos utilizando el metodo HTTP GET a un directorio con el nombre del mod o a uno que se le agrega _X siendo X las veces que el directorio existe
- Identifica la extension del archivo identificando la cabecera leyendo los primeros 16 Kilobytes del archivo y comparandolos con extension de archivos conocidos de TTS
- Simula un navegador para los sitios de hosting de imagenes y reintenta la descarga de archivos si esta falla
- Guarda automaticamente patron,url,archivo en un archivo CSV
- Descarga archivos validos de TTS como imagenes,pdf y modelos 3d, omite el resto
- Verifica que la libreria request este instalada al ejecutar el script



## Requisitos
- **Python**: Versión 3.6 o superior.
- **Librería `requests`**:
```bash
 pip install requests
```
   


