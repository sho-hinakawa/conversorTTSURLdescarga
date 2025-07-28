# Descargador de archivos de TTS desde el ID del Workshop 

Este script en Python permite descargan los archivos de un mod del Workshop de Tabletop Simulator dado el ID a un directorio dado por el nombre del mod

**Creditos** Telegram @hinakawa y @alemarfar

## Caracteristicas
- Lee el ID desde el Workshop de TTS especificado por el usuario
- Realiza la conversion a archivo obteniendo los campo de datos terminados en URL y su url
- Realiza reemplazo de las url con las URLs validas para descargar
- Verifica que sean URLs unicas
- Detecta extensiones de los archivos segun su cabecera descargada y le asiga el MIME Type correspondiente
  a los correspondientes a TTS
- Descarga las URLs indicando nombre del campo de datos utilizando el metodo HTTP GET a un directorio especificado por el usuario
- Identifica la extension del archivo identificando la cabecera leyendo los primeros 4096 bytes del archivo y comparandolos con archivos conocidos de TTS
- Descarga a un directorio con el mismo nombre que el mod de TTS o uno que elija el usuario
- Posee metodo debug para entregar mensajes en pantalla, guardar errores 

## Requisitos
- **Python**: Versión 3.6 o superior.
- **Librería `requests`**:
```bash
 pip install requests
```
   

