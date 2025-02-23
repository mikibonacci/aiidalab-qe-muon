# aiidalab-qe-muon
Plugin to compute muon stopping sites and related properties via the aiida-muon and aiida-musconv AiiDA plugins

## Installation

In order to load this plugin into QeApp, you need to switch to the `main` branch for your `aiidalab-qe`.

Then, install this plugin by:

```shell
pip install -e .
```

To also install the needed codes, if not already there, you can then run:

```shell
install_muon_codes
```

To automatically (nb: you can do it also by hands) install on a local/remote computer (already set up in AiiDA) the needed conda environment for [undi](https://undi.readthedocs.io/en/latest/index.html) calculations,
open a verdi shell and run:

```python
from aiida_pythonjob.utils import create_conda_env

computer_label = "<computer_label>" # Remote computer label, already stored in the AiiDA database
env_name = "<environment_name>"     # Desired name of the conda environment you are going to create

```python
create_conda_env(
    computer_label,          
    env_name,         
    modules=[],                   # Modules to be loaded in order to invoke conda
    pip=[
        "numpy~=1.26",
        "ase",
        "tqdm",
        "pandas",
        "pybind11",
        "git+https://github.com/mikibonacci/undi.git@update",
        ],  # Python packages to be installed via pip
    conda={                   # Conda-specific settings
        "channels": ["conda-forge"],  # Channels to use
        "dependencies": ["cloudpickle"] # package to install using conda
    },
    install_conda=True,
)
```

for more details on this procedure, see the official `aiida-pythonjob` [documentation](https://aiida-pythonjob.readthedocs.io/en/latest/autogen/how_to.html#create-a-conda-environment-on-the-remote-computer).

## License

MIT

## Contact

miki.bonacci@psi.ch


## Acknowledgements
We acknowledge support from:
* the [NCCR MARVEL](http://nccr-marvel.ch/) funded by the Swiss National Science Foundation;
* the PNRR MUR project [ECS-00000033-ECOSISTER](https://ecosister.it/);

<img src="https://raw.githubusercontent.com/positivemuon/aiida-muon/main/docs/source/images/MARVEL_logo.png" width="250px" height="131px"/>
<img src="https://raw.githubusercontent.com/positivemuon/aiida-muon/main/docs/source/images/ecosister_logo.png" width="300px" height="84px"/>
