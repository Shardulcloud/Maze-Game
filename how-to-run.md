# How to Run Maze Runner

## Windows

Open **Command Prompt** or **PowerShell**, then go to the project folder. Replace the path if you saved the project elsewhere:

```powershell
cd "$HOME\Desktop\shardul\maze-game"
```

Run the Windows launcher:

```powershell
.\run.bat
```

It creates `.venv`, installs dependencies, and starts the game. No virtual-environment activation is needed.

Start a specific mode/configuration:

```powershell
.\run.bat --mode coop --size large --gen wilson --seed 42
```

Run tests and benchmarks:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe benchmarks\run_all.py --quick
```

For the headless smoke test in PowerShell:

```powershell
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"
.\.venv\Scripts\python.exe -m game.main --smoke
Remove-Item Env:SDL_VIDEODRIVER, Env:SDL_AUDIODRIVER
```

Requires Python 3.9+ on PATH. Install from [python.org](https://www.python.org/downloads/windows/) and enable **Add Python to PATH** during setup.

## macOS / Linux

### 1. Open project folder

```bash
cd /Users/ranknwar/Desktop/shardul/maze-game
```

If your terminal already shows `maze-game %`, you are already inside the project. Do **not** run `cd maze-game` again.

### 2. Run game

Recommended:

```bash
./run.sh
```

This script:

- creates/uses `.venv`
- installs dependencies from `requirements.txt`
- starts the game

### 3. Run with manual commands

If you do not want to use `run.sh`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m game.main
```

### 4. Start specific mode

```bash
./run.sh --mode solo
./run.sh --mode race
./run.sh --mode coop
```

With size, generator, and seed:

```bash
./run.sh --mode coop --size large --gen wilson --seed 42
```

Options:

```bash
./run.sh --help
```

### 5. Controls

### Menu

| Key | Action |
|---|---|
| `UP/DOWN` | choose menu row |
| `LEFT/RIGHT` | change option |
| `R` | reroll seed |
| `ENTER` or `SPACE` | start game |
| `ESC` | quit |

### Game

| Key | Action |
|---|---|
| `WASD` | Player 1 movement |
| Arrow keys | Player 2 movement |
| `H` | A* hint, if mode allows it |
| `ESC` | pause |
| `R` | restart same maze |
| `N` | new maze |

### 6. Game modes

| Mode | Command | Description |
|---|---|---|
| Solo | `./run.sh --mode solo` | one player, fog of war, hints |
| Race | `./run.sh --mode race` | two players, first to exit wins |
| Co-op | `./run.sh --mode coop` | split-screen navigator + runner |

### 7. Maze generators

```bash
./run.sh --gen dfs
./run.sh --gen prim
./run.sh --gen kruskal
./run.sh --gen wilson
./run.sh --gen division
```

### 8. Run tests

```bash
source .venv/bin/activate
python -m unittest discover -s tests
```

Expected result:

```text
Ran 42 tests
OK
```

### 9. Run smoke test

Headless end-to-end check:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy python -m game.main --smoke
```

Expected result:

```text
SMOKE OK
```

### 10. Run benchmarks

Quick benchmark:

```bash
python benchmarks/run_all.py --quick
```

Full benchmark:

```bash
python benchmarks/run_all.py
```

Results are saved in:

```text
benchmarks/results/
```

### 11. Regenerate sounds

Normally automatic. Manual command:

```bash
python tools/generate_sounds.py
```

Generated files go to:

```text
assets/sounds/
```

## Troubleshooting

### `cd: no such file or directory: maze-game`

You are probably already inside the folder.

Check:

```bash
pwd
```

If it ends with `/maze-game`, run:

```bash
./run.sh
```

Not:

```bash
cd maze-game && ./run.sh
```

### `Permission denied: ./run.sh`

Run:

```bash
chmod +x run.sh
./run.sh
```

### Pygame not found

Run:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

### No sound

Game still works. To regenerate sound files:

```bash
python tools/generate_sounds.py
```
