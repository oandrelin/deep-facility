# Digitally Enabled Equitably Placed (DEEP) Facility  
Tools for optimizing placement of health workers and services based on village locations.  

## Prerequisites
- [Python](https://www.python.org/downloads) 3.12 or higher.
- [Python virtual environment](https://realpython.com/python-virtual-environments-a-primer/)

## Setup
This section describes how to set up the tool and the demo web app.
 
1. Activate your Python virtual environment and upgrade pip and build tools.
```bash
# Update pip and build package.
pip install --upgrade pip  
pip install --upgrade build
pip install --upgrade setuptools
```

2. [Clone this repository](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) or [download](https://github.com/InstituteforDiseaseModeling/deepfacility/archive/refs/heads/main.zip) and extract the source code. Then open a terminal and navigate to the root directory of the source code.
```bash
# Navigate to the root directory.
cd deepfacility
``` 

3. Install the tool:  
```bash
# Install the tool and required packages. 
pip install -e .
```

## Getting Started

Start the demo web app:
```bash
# Start the demo web app using `ux` command.
deepfacility ux
````

After you see the message `Serving on ...` the **demo** web app is running.   

Follow these steps to experience the workflow end-to-end:
- Open your web browser and navigate to [http://localhost:8000](http://localhost:8000) to access the **demo** web app.
- Follow instructions to "upload" and configure village locations .csv file.
  - _Note that this app is running on your local machine and all files are stored locally._ 
- Click `Prepare Data` to download and prepare input data: households and commune shapes. 
- Select locations (communes) and click `Run Clustering` to start the processing.
- Visualize and explore village shapes and health facilities recommendations on a map.
- Obtain the results file.

_Notes_: 
- _This web app is only for **demo** purposes and is **not** intended for production use._
- _To start a fresh copy of the app, without cached data, run `deepfacility reset` command before starting the app._

# Terminology
In this repository, we use the following terms and abbreviations:

- `Cluster` and `Village` refer to the same entity with small differences in context:
  - Cluster: a group of households. 
  - Village: spatial interpretation of a cluster.
- `Location`: an administrative area where the clustering is performed.
  - In this tool a location value is a colon-separated list of names of administrative levels, per [configuration](docs/design.md#locations).
  - For example, in Burkina Faso:
    - `Tapoa:Diapaga` represents the `Diapaga` commune from the `Tapoa` province.
    - `Tapoa:Diapaga:Mangou` represents a village from the `Diapaga` commune. 

- Abbreviations:
  - Health Facilities (HF)
  - Empirical Cumulative Distribution Function (eCDF)

# Multi-Language Support
By default, the demo web app supports French and English languages. To add a support for additional languages see [Add New Language](docs/design.md#adding-new-languages) section in the design document.

## Documentation
- [Components](docs/components.md)  
- [Design](docs/design.md)  
- [Scientific Workflow](docs/workflow.md)
- [CLI commands](docs/commands.md)

## Data Sources
The system is using the following external data sources: 
- <a href="https://sites.research.google/open-buildings">Open Buildings</a> (Google)   
  <cite>W. Sirko, S. Kashubin, M. Ritter, A. Annkah, Y.S.E. Bouchareb, Y. Dauphin, D. Keysers, M. Neumann, M. Cisse, J.A. Quinn. Continental-scale building detection from high resolution satellite imagery. <a href="https://arxiv.org/abs/2107.12283">arXiv:2107.12283</a>, 2021.</cite>

- [GADM shapes](https://gadm.org/data.html) for countries administrative areas 

## Package Dependencies
Packages listed in
[pyproject.toml](pyproject.toml)

## Disclaimer
The code in this repository was developed by IDM to support our research into healthcare system capacity. We’ve made it publicly available under the MIT License to provide others with a better understanding of our research and an opportunity to build upon it for their own work. We make no representations that the code works as intended or that we will provide support, address issues that are found, or accept pull requests. You are welcome to create your own fork and modify the code to suit your own modeling needs as contemplated under the MIT License.

