# Entorno de la máquina (WSL2) — referencia para trabajo con Python

> Este archivo documenta el entorno del sistema (no específico de `enbici`), para que cualquier
> agente/sesión futura sepa qué herramientas hay instaladas, cuál usar en cada proyecto, y cómo
> evitar los problemas de venvs "perdidos" en otras carpetas.

## Plataforma

- **WSL2** sobre Windows, distro **Ubuntu 24.04.4 LTS**, kernel `6.18.33.2-microsoft-standard-WSL2`.
- Shell: `bash`.
- Home: `/home/martinferreirab`.
- Los proyectos viven bajo `/home/martinferreirab/proyectos/<nombre>`.

## Gestores de Python/paquetes instalados

| Herramienta | Ubicación | Estado |
|---|---|---|
| **uv** | `~/.local/bin/uv` (v0.12.0) | Instalado y en uso activo en `enbici` |
| **Poetry** | `~/.local/bin/poetry` (v2.4.1) | Instalado 2026-08-12, para proyectos nuevos |
| **conda** (miniconda3) | `~/miniconda3` | Instalado, `auto_activate_base = False` (no se activa solo en cada shell — bien, evita interferir con uv/poetry) |
| **pip/pip3 del sistema** | no hay binario global standalone | No usar pip a mano fuera de un venv/proyecto gestionado |
| **Python del sistema** | `/usr/bin/python3.12` → Python 3.12.3 | Base que usan uv/poetry para crear venvs |

**Regla de convivencia**: no mezclar gestores dentro de un mismo proyecto. Cada proyecto usa **uno**
(uv o poetry), nunca ambos, y nunca pip manual + venv manual por fuera de ellos.

## Por qué había dolor de cabeza con venv

El patrón anterior era `python -m venv` creando el entorno en una carpeta separada del proyecto
(o en el home), lo que hacía fácil perder de vista qué venv correspondía a qué proyecto, activar
el equivocado, o que el intérprete de VSCode apuntara a otro lado. Los dos gestores actuales
resuelven esto activando el patrón "el entorno vive junto al código":

- **uv**: crea `.venv/` en la raíz del proyecto por defecto.
- **Poetry**: configurado (2026-08-12) con `virtualenvs.in-project = true`, así que también crea
  `.venv/` dentro del proyecto en vez de en `~/.cache/pypoetry/virtualenvs/`. Ver sección Poetry.

## uv — cómo se usa (proyecto `enbici` y similares)

```bash
uv sync              # instala deps según pyproject.toml + uv.lock, crea .venv/ en el proyecto
uv add <paquete>     # agrega dependencia
uv remove <paquete>  # quita dependencia
uv run <comando>     # corre un comando dentro del venv del proyecto sin activarlo a mano
uv python list       # lista versiones de Python disponibles/descargables (uv puede bajar su propio Python)
```

- `enbici` tiene `[tool.uv] package = false` en `pyproject.toml` (no es un paquete instalable, es una app).
- El build backend es `uv_build`.
- **No usar `pip install` a mano** ni crear venvs con `python -m venv` en proyectos uv — todo pasa
  por `uv add`/`uv sync`.
- Boot rápido porque uv resuelve con lockfile (`uv.lock`), reproducible entre máquinas.

## Poetry — instalado 2026-08-12, para proyectos nuevos

Instalado con el instalador oficial (`curl -sSL https://install.python-poetry.org | python3 -`),
que lo deja en `~/.local/bin/poetry` (ya está en el `PATH` vía `~/.profile`, sin pasos extra).

Configuración global aplicada:

```bash
poetry config virtualenvs.in-project true
```

Con esto, **todo proyecto nuevo con Poetry** crea su entorno en `<proyecto>/.venv/` en vez de en
`~/.cache/pypoetry/virtualenvs/<hash>/`. Esta es la config clave para no volver a perder venvs.

Comandos típicos:

```bash
poetry init                 # crea pyproject.toml en un proyecto existente (interactivo)
poetry new <nombre>         # crea un proyecto nuevo desde cero con estructura estándar
poetry add <paquete>        # agrega dependencia (crea .venv en el proyecto si no existe)
poetry install               # instala según pyproject.toml + poetry.lock
poetry run <comando>         # corre un comando dentro del venv del proyecto
poetry shell                 # (si está el plugin shell) abre una shell con el venv activado
poetry env info               # muestra dónde está el venv activo — usar esto si hay dudas de qué entorno se está usando
```

- `enbici` **no** se migró a Poetry — sigue con uv (decisión 2026-08-12, ver `tip_skills.md` regla
  #3 y `journey.md`). Poetry queda disponible para proyectos nuevos que el usuario cree en esta
  máquina.
- Si en el futuro se quiere migrar un proyecto de uv a Poetry: borrar `.venv/` y `uv.lock`,
  convertir `[project]`/`dependencies` de `pyproject.toml` al formato de Poetry (`poetry init`
  puede generar la sección `[tool.poetry]`, o usar `[project]` con PEP 621 si la versión de
  Poetry lo soporta — Poetry 2.x soporta `[project]` directamente).

## conda

- Miniconda instalado en `~/miniconda3`, inicializado en `~/.bashrc` (bloque `# >>> conda
  initialize >>>`).
- `auto_activate_base` está en `False` — el entorno `base` de conda **no** se activa solo al abrir
  una shell nueva. Esto es intencional/bueno: evita que el `python`/`pip` de conda tape al de
  uv/poetry en el `PATH`.
- Si algún día un proyecto necesita conda específicamente (p. ej. paquetes científicos pesados que
  no están bien empaquetados en PyPI), usar `conda activate <env>` explícitamente, no depender de
  auto-activate.

## Convención sugerida para proyectos nuevos en esta máquina

1. ¿El proyecto necesita paquetes que solo existen bien resueltos vía conda (raro, típicamente
   geoespacial/científico pesado con binarios nativos)? → conda, entorno con nombre propio.
2. Si no → **Poetry** por defecto para proyectos nuevos (venv in-project ya configurado).
3. `enbici` y cualquier otro proyecto ya migrado a **uv** se queda en uv — no mezclar gestores en
   un proyecto ya andando.
4. Nunca `python -m venv` manual ni `pip install` global fuera de un entorno gestionado por
   uv/poetry/conda.

## Cómo verificar en qué entorno estás parado (debugging rápido)

```bash
which python3           # ver qué intérprete resuelve el shell actual
python3 -c "import sys; print(sys.executable)"
poetry env info          # si el proyecto es Poetry
uv python list            # ver pythons que uv conoce/gestiona
conda env list            # ver envs de conda y cuál está activo (marcado con *)
```
