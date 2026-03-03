# helios-core

RBMK reactor control station simulator with a packaged CLI for `pipx`.

## Install

```bash
pipx install .
```

## Commands

```bash
helios-core                 # Launch GUI
helios-core gui             # Launch GUI
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
python channel-deviation-view.py
```
