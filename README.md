# helios-core

Helios is a control system for a RBMK style reactor. It can be run as a standalone simulation, or as a server, and I'm making a model

## Install
[ PIPX INSTALL IS STILL ENTIRELY BROKEN, GIT CLONE THE REOP AND RUN PIPX INSTALL . ]
```bash
pipx install helios-core
```
or
```bash
pip install helios-core
```

## Commands

```bash
helios-core                 # Launch GUI
helios-core gui             # Launch GUI
helios-core --server=http://127.0.0.1:8000   # GUI with backend server
helios-core tui             # Launch Textual TUI
helios-core tui --server=http://127.0.0.1:8000
helios-core serve           # Run server only (no GUI)
helios-core serve --port 8000
helios-core map             # Print reactor core map
helios-core stats           # Show rod counts and utilization
helios-core rod-types       # List rod type codes
helios-core estimate 100    # Estimate thermal/electrical output
helios-core guide           # Show packaged operator guide path
helios-core guide --print   # Print operator guide text
```

## Backward compatibility

The original launcher script remains available:

```bash
python main.py
python channel-deviation-view.py
```
