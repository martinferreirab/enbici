# Journey App: enbici_app (Android/Expo)

## Estado actual
- **Fase:** Iniciando port a React Native/Expo.
- **SDK:** Expo SDK 54.0.0.
- **Estado de bloqueo:** Error persistente `Invariant Violation: PlatformConstants could not be found`.
- **Última acción:** Actualización manual de `package.json` para alinear con SDK 54, limpieza de dependencias, deshabilitación de React Compiler.

## Historial de errores y soluciones (Contexto técnico)
1. **Error: `libnspr4.so` missing:** Al correr `npx expo start --tunnel` en WSL/Ubuntu.
   - *Solución:* Ignorado (es un warning de devtools en Linux), la app funciona sin el debugger de escritorio.
2. **Error: `Incompatible SDK version`:** Expo Go pedía SDK 54, el proyecto estaba en 51.
   - *Solución:* Actualizado `package.json` y `app.json` a SDK 54.
3. **Error: `Unable to resolve "react/compiler-runtime"`:** Conflicto con React Compiler habilitado en un proyecto que no lo soportaba.
   - *Solución:* Deshabilitado `reactCompiler: false` en `app.json` y limpieza de `babel.config.js`.
4. **Error: `Unable to resolve "react-native-worklets"`:** Importado automáticamente en `AnimatedSplashOverlay`.
   - *Solución:* Eliminada la importación y el componente del `_layout.tsx` para simplificar el arranque.
5. **Bloqueador actual:** `Invariant Violation: PlatformConstants could not be found`.
   - *Hipótesis:* Desincronización profunda entre los archivos compilados en Metro y la versión de React Native instalada tras la actualización manual de `package.json`.

## Reglas de Arquitectura
- **Map-First:** WebView full-screen como capa base.
- **Backend:** Conexión a `http://172.30.108.170:8000` (ajustar según IP local si falla).
- **Modos de red:** Priorizar `npx expo start --clear --tunnel` para evitar errores de red de WSL2.

## Roadmap (Tareas pendientes)
1. **Resolver bloqueo `PlatformConstants`:**
   - Verificar si `metro.config.js` necesita resetearse.
   - Considerar limpiar `~/.npm` o `~/.expo` si el error persiste.
2. **Integración API (`src/services/api.ts`):** Implementar cliente Fetch para `GET /route`.
3. **Construcción UI:**
   - Crear `MapViewer.tsx` (WebView wrapper).
   - Crear `TopSearchBar.tsx` y `FilterModal.tsx`.
   - Crear `BottomSheet.tsx`.
4. **Conexión Final:** Integrar lógica de cálculo y visualización de métricas.

## Notas para el agente
- La app usa Expo Router (File-based routing).
- No intentar usar `react-native-worklets` ni configuraciones de compilador experimental.
- Ante cualquier error de "native binary" o "module not found", priorizar `npx expo start --clear`.