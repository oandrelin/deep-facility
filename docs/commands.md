# Command Line Tool Commands

## Setup
Follow the [setup instruction](../README.md#setup) from the README.

## Configuration
Confirm the tool has been installed and observe the help content:  
```bash  
# Check the tool has been installed and see the usage help.
deepfacility

> usage: deepfacility run [-h] [-l LOCATION_FILTER [LOCATION_FILTER ...]] [-c CONFIG_FILE] [-n RUN_NAME] [-r RESULT_DIR] [--sid SESSION_ID]
                        {countries,config,prep,locations,run,viewmap,ux,reset}  
```  

See the list of supported countries:  
```bash 
deepfacility countries

> INFO: Supported countries (you can set in config):
> ...list of countries...
```

Create a config file:   
```bash
# Generate a config file at the default path: app-data/config.toml
deepfacility config 
```

Update the config file to set paths and column names for your files:
- `[args.village_centers]` section for the village centers file. 
- `[args.baseline_facilities]` section for the baseline facilities file (this is optional).

## Data Preparation

Prepare scientific workflow input files:
```bash  
# Prepare input files
deepfacility prep  
```  
The above command will:
- download and preprocess Google buildings and GADM shapes
- standardize your village centers and baseline facilities files

## Scientific Workflow

See the list of all available locations execute the `locations` command:
```bash
# Read all locations available in the input data.
deepfacility locations
```
_Note: The filter can be a specific location or a location [regex](https://docs.python.org/3/howto/regex.html#regex-howto) pattern._

Process specified subset of locations.   
```bash  
# Run the processing for a subset of locations.
deepfacility run -l "Noumbiel:.*"  # All locations in the Noumbiel province
```

To process all locations execute the `run` command without a location filter (this may take 1-2h). 

## Visualizing Results
Generate the interactive visualization map by specifying the result directory:
```bash
# Create viz map for results generated with -l `Noumbiel:.*`
deepfacility viewmap -r Noumbiel-_1_5a819a9 
````
_Note: Look at the `app-data/data/BFA/results` directory for the list of available results directories._ 

## Testing
Install the test dependencies:  
```bash
# Install test dependencies.
pip install -e .[test]
```
Run available tests:   
```bash  
pytest -v  
```  
