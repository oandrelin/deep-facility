# Scientific Workflow Diagram
The below diagram illustrates the scientific workflow this tool performs. 

_Note: The diagram uses terms and abbreviations describes in the [Terminology](../README.md#terminology) section in the main README._

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#eeffcfff',
      'primaryTextColor': 'black',
      'primaryBorderColor': 'black',
      'lineColor': '#789abc',
      'secondaryColor': '#006100',
      'tertiaryColor': '#ffffff',
      'tertiaryBorderColor': 'lightgray'
    }
  }
}%%
graph TD
    ready_inputs((<b>Inputs</b>
            Admin shapes and locations
            Building coordinates
            Village center coordinates
            Baseline facilities coordinates)) -->
            
            cluster_houses["<b>Cluster Houses</b>
            Group households into clusters using KMeans algorithm, 
            initializing cluster centers with input villages centers.
            The result are clusters (villages), each containing 
            a subset of input households."] -->
            
                village_shapes["<b>Create Village Shapes</b>
                Create village shapes by calculating 
                 convex hull around household points 
                for each village cluster."] -->
                
                result_files(("<b>Result Files</b>
                            Locations file
                            Clustered Households file
                            Village Shapes GeoJson file
                            HF Optimal Placements file
                            HF Population Coverage Plots
                            Logs"));
                
            cluster_houses -->
                recommend_locations["<b>Recommend Facility Placement</b>
                Performs KMeans clustering of village households
                to find a specified number of points (e.g., 3) that are
                optimally distant from all village households."] -->
                
                calculate_distances["<b>Calculate Minkowski Distances</b>
                Calculate Minkowski distances between 
                households and nearest HF for existing (baseline) 
                and optimal HF placements."] -->
                
                    plot_location_distances["<b>Plot Commune HF Population Coverage</b>
                    Plot optimal and baseline commune population coverage 
                    using eCDF based on calculated Minkowski distances."] -->
            
            calculate_distances -->
                merge_results["<b>Merge Results</b>
                Merge commune result files. 
                See 'Result Files' for details."] --> result_files;

    merge_results --> plot_merged_results["<b>Plot Overall HF Population Coverage</b>
                    Support HF placement decision making by
                    plotting optimal and baseline population coverage using eCDF 
                    based on Minkowski distances calculated on merged data."] --> result_files;
;
```
`Clustered Households` file contains:
  - cluster centers
  - cluster-household mapping
  - cluster-household counts statistics 
    - Descriptive statistics of cluster-household counts
    - % of small villages (with less than )
    - Total number of villages
