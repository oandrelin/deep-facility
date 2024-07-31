has_baseline = typeof baseline_facilities != 'undefined' && baseline_facilities !== null

var highlightLayer;
function highlightFeature(e) {
    highlightLayer = e.target;
    highlightLayer.openPopup();
    highlightLayer.bringToFront();
}

var popupOptions = {
    autoClose: false,    // Prevent automatic closing when opening another popup
    closeOnClick: false  // Prevent closing when clicking outside the popup
};

const mapDiv = document.getElementById("map");
// Creating leaflet map element
map = L.map('map', {
    zoomControl:true,
    maxZoom:28,
    minZoom:5,
    loadingControl: true
});

const resizeObserver = new ResizeObserver(() => {
  map.invalidateSize();
});

resizeObserver.observe(mapDiv);

// Create tile layers
var layer_satellite = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    minZoom: 5,
    maxZoom: 28,
    opacity: 0.75,
    attribution: 'Tiles © Esri — Source: Esri, i-cubed, USDA, USGS, AEX, GeoEye, Getmapping, Aerogrid, IGN, IGP, UPR-EGP, and the GIS User Community'
});
var layer_osm = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    minZoom: 5,
    maxZoom: 28,
    opacity: 0.75,
    attribution: '© OpenStreetMap contributors'
});
var layer_topo = L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    minZoom: 5,
    maxZoom: 28,
    opacity: 0.75,
    attribution: 'Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)'
});

var baseMaps = {
    "OpenStreetMap": layer_osm,
    "Satellite": layer_satellite,
    "Topology": layer_topo
};
map.addLayer(layer_osm);
var mapLayerControl = L.control.layers(baseMaps).addTo(map);

// Create custom Checkbox for layer controls in the topright section
var layer_controls = L.control({position: 'topright'});

layer_controls.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'command');

    div.innerHTML = '<form><input id="household_shade" type="checkbox"/><span style="font-size: 20px;">{{ _("show household population") }}</span></form>';
    return div;
};

layer_controls.addTo(map);


// Column_name_definition based on deepfacility output
adm2_col = 'adm2'
adm3_col = 'adm3'
adm4_col = 'adm4'
cluster_col = 'cluster'
household_col = 'households'
plus_col = 'plus'
lon_col = 'lon'
lat_col = 'lat'
info_col = 'info_col'
gadm_adm0_col = 'COUNTRY'
gadm_adm1_col = 'NAME_1'
gadm_adm2_col = 'NAME_2'
gadm_adm3_col = 'NAME_3'
show_household_shade = false


// Variables to hold the selected adm2 and adm3 values
var adm2, adm3;
var adm3Values = []

// Get the unique adm2 values based on optimal_facilities and populate the adm2 select element
var adm2Values = [...new Set(optimal_facilities.features.map(feature => feature.properties.adm2))];
var adm3ValuesAll = [...new Set(optimal_facilities.features.map(feature => feature.properties.adm3))];


var adm2Select = document.getElementById('adm2Select');
adm2Values.forEach(value => {
    var option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    adm2Select.appendChild(option);
});
adm2Select.disabled = false;  // Enable the adm2 select element

// Add an event listener to the adm2 select element to populate new adm3 values
adm2Select.addEventListener('change', function() {
    adm2 = this.value;  // Store the selected adm2 value
    // Get the unique adm3 values for the selected adm2 value and populate the adm3 select element
    adm3Values = [...new Set(optimal_facilities.features.filter(feature => feature.properties[adm2_col] === adm2).map(feature => feature.properties[adm3_col]))];
    var adm3Select = document.getElementById('adm3Select');
    adm3Select.innerHTML = '<option value="">{{ _("Select") }} ADM3</option>';  // Clear any previous adm3 values
    adm3Values.forEach(value => {
        var option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        adm3Select.appendChild(option);
    });
    adm3Select.disabled = false;  // Enable the adm3 select element
});

// Add an event listener to the adm3 select element
document.getElementById('adm3Select').addEventListener('change', function() {
    adm3 = this.value;  // Store the selected adm3 value
    console.log('Selected ADM2:', adm2, 'Selected ADM3:', adm3);  // Log the selected values to the console
});

function locationFilter2(feature) {
    if(adm2Values.includes(feature.properties[adm2_col]) && adm3ValuesAll.includes(feature.properties[adm3_col])) {
        return locationFilter(feature)   
    }
}

// Filter for GeoJSON
function locationFilter(feature) {
    if (adm2 == null || adm2 == "") {
        return true
    }
    if (feature.properties[adm2_col] == adm2){
        if (adm3 == null || adm3 == "") return true
        if (feature.properties[adm3_col] == adm3) return true
    }
}

// handle click to filter adm2/adm2 locations
document.getElementById('filter_loc').onclick = function(){
    document.getElementById("household_shade").checked = false;
    show_household_shade = false;
    map.removeLayer(layer_optimal_facilities)
    layer_optimal_facilities = add_layer_optimal_facilities()
    map.addLayer(layer_optimal_facilities)

    map.removeLayer(layer_village_shapes)
    layer_village_shapes = add_layer_village_shapes()
    map.addLayer(layer_village_shapes)

    map.removeLayer(layer_village_centers);
    layer_village_centers = add_layer_village_centers()
    map.addLayer(layer_village_centers);
        
    if (has_baseline) {
        map.removeLayer(layer_baseline_facilities);
        layer_baseline_facilities = add_layer_baseline_facilities()
        map.addLayer(layer_baseline_facilities);
    }
    
    mapLayerControl.removeLayer(group_optimal_facilities);
    mapLayerControl.removeLayer(group_village_center);
    if (has_baseline) mapLayerControl.removeLayer(group_baseline_facilities);
    group_optimal_facilities = L.layerGroup([layer_optimal_facilities]).addTo(map);
    mapLayerControl.addOverlay(group_optimal_facilities, "{{ _("Optimal Facilities") }}");
    group_village_center = L.layerGroup([layer_village_centers]).addTo(map);
    mapLayerControl.addOverlay(group_village_center, "{{ _("Village Centers") }}");
    if (has_baseline) {
        group_baseline_facilities = L.layerGroup([layer_baseline_facilities]).addTo(map);
        mapLayerControl.addOverlay(group_baseline_facilities, "{{ _("Baseline Facilities") }}");
    }
};

var hash = new L.Hash(map);
map.attributionControl.setPrefix('<a href="https://github.com/tomchadwin/qgis2web" target="_blank">qgis2web</a> &middot; <a href="https://leafletjs.com" title="A JS library for interactive maps">Leaflet</a> &middot; <a href="https://qgis.org">QGIS</a>');
var autolinker = new Autolinker({truncate: {length: 30, location: 'smart'}});
var bounds_group = new L.featureGroup([]);

/******
 * Village shapes
 ******/

function pop_village_shapes(feature, layer) {
    layer.on({
        mouseclick: highlightFeature,
    });
    var popupContent = '<table>\
            <tr>\
                <td>{{ _("Village Shape") }}</td>\
            </tr>\
            <tr>\
                <th scope="row">adm2</th>\
                <td colspan="2">' + (feature.properties[adm2_col] !== null ? autolinker.link(feature.properties[adm2_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">adm3</th>\
                <td colspan="2">' + (feature.properties[adm3_col] !== null ? autolinker.link(feature.properties[adm3_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">village</th>\
                <td colspan="2">' + (feature.properties[adm4_col] !== null ? autolinker.link(feature.properties[adm4_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">cluster</th>\
                <td colspan="2">' + (feature.properties[cluster_col] !== null ? autolinker.link(feature.properties[cluster_col].toLocaleString()) : '') + '</td>\
            </tr>\
             <tr>\
                <th scope="row">household count</th>\
                <td colspan="2">' + (feature.properties[household_col] !== null ? autolinker.link(feature.properties[household_col].toLocaleString()) : '') + '</td>\
            </tr>\
        </table>' 
    var finalContent = `${popupContent}<br>
    <img src="./images/${feature.properties[adm2_col]}_${feature.properties[adm3_col]}_clustered_households.png" width="100" 
             onclick="this.style.width = this.style.width === '330px' ? '100px' : '330px';"
             onerror="this.style.display='none';" style="cursor: pointer;">
    `;
    if(has_baseline){
    finalContent +=`<img src="./images/${feature.properties[adm2_col]}_${feature.properties[adm3_col]}_population_coverage_baseline.png" width="100" 
             onclick="this.style.width = this.style.width === '330px' ? '100px' : '330px';"
             onerror="this.style.display='none';" style="cursor: pointer;">
    `; 
    }    
    layer.bindPopup(finalContent, popupOptions, {maxHeight: 400});
}

 
 var legend = L.control({position: 'topleft'});
 
// Add event handler for color selection
function handleHousehold_shade() {
    if (household_shade.checked){
      show_household_shade = true
      // show legend for household color
      legend.onAdd = function (map) {
        var div = L.DomUtil.create('div', 'info legend'),
            grades = [0, 100, 500, 1000, 10000],
            labels = [];
        div.innerHTML = '<b>{{ _("Village Households") }}</b><br>'
        // loop through household sizes and generate a label with a colored square for each interval
        for (var i = 0; i < grades.length; i++) {
            div.innerHTML +=
                '<i style="font-size:16px; color:red; opacity: 0.6; background-color:' + getColor(grades[i] + 1) + '">' +
                grades[i] + (grades[i + 1] ? '&ndash;' + grades[i + 1] + '<br>' : '+');
        }
        return div;
      };
      legend.addTo(map);
      
    }
    else{
      show_household_shade = false
      legend.remove()
    }
    map.removeLayer(layer_village_shapes);
    layer_village_shapes = add_layer_village_shapes()
    map.addLayer(layer_village_shapes);
    map.fitBounds(layer_village_shapes.getBounds());
}
document.getElementById ("household_shade").addEventListener("change", handleHousehold_shade);

function getColor(d) {
    if (show_household_shade){
      return d > 10000  ? '#000080':
           d > 1000   ? '#0000FF' :
           d > 500   ? '#0096FF' :
           d > 100   ? '#89CFF0' :
                      '#DEFFFF';
    }
    else{
        return '#89CFF0'
    }    
} 



function style_village_shapes(feature) {
    return {
        pane: 'pane_village_shapes',
        opacity: 0.5,
        color: 'rgba(35,35,35,1.0)',
        dashArray: '',
        lineCap: 'butt',
        lineJoin: 'miter',
        weight: 1,
        fill: true,
        fillOpacity: 0.3,
        fillColor: getColor(feature.properties[household_col]),
        interactive: true,
    }
}
map.createPane('pane_village_shapes');
map.getPane('pane_village_shapes').style.zIndex = 401;
map.getPane('pane_village_shapes').style['mix-blend-mode'] = 'normal';

function add_layer_village_shapes() {
    var layer= new L.geoJson(village_shapes, {
        attribution: '',
        interactive: false,
        dataVar: 'json_village_shapes',
        layerName: 'layer_village_shapes',
        pane: 'pane_village_shapes',
        filter: locationFilter,
        onEachFeature: pop_village_shapes,
        style: style_village_shapes,
    });
    return layer
}
layer_village_shapes = add_layer_village_shapes()
// bounds_group.addLayer(layer_village_shapes);
map.addLayer(layer_village_shapes);
map.fitBounds(layer_village_shapes.getBounds());

/******
 * Optimal facilities
 ******/
function pop_optimal_facilities(feature, layer) {
    layer.on({
        mouseclick: highlightFeature,
    });
    var popupContent = '<table>\
            <tr>\
            <td>{{ _("Health Facility") }}<td>\
            </tr>\
            <tr>\
                <th scope="row">adm2</th>\
                <td>' + (feature.properties[adm2_col] !== null ? autolinker.link(feature.properties[adm2_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">adm3</th>\
                <td>' + (feature.properties[adm3_col] !== null ? autolinker.link(feature.properties[adm3_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">adm4</th>\
                <td>' + (feature.properties[adm4_col] !== null ? autolinker.link(feature.properties[adm4_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">lon</th>\
                <td>' + (feature.properties[lon_col] !== null ? autolinker.link(feature.properties[lon_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">lat</th>\
                <td>' + (feature.properties[lat_col] !== null ? autolinker.link(feature.properties[lat_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">plus</th>\
                <td><a href="http://www.google.com/maps/place/' + (feature.properties[plus_col] !== null ? autolinker.link(feature.properties[plus_col].toLocaleString().replace('+', '%2B')) : '') + '" target="_blank">' + (feature.properties[plus_col] !== null ? autolinker.link(feature.properties[plus_col].toLocaleString()) : '') + '</a></td>\
            </tr>\
        </table>';
    layer.bindPopup(popupContent, {maxHeight: 400});
}


map.createPane('pane_optimal_facilities');
map.getPane('pane_optimal_facilities').style.zIndex = 402;
map.getPane('pane_optimal_facilities').style['mix-blend-mode'] = 'normal';

function add_layer_optimal_facilities(){
    var layer = new L.geoJson(optimal_facilities, {
        attribution: '',
        interactive: true,
        dataVar: 'json_optimal_facilities',
        layerName: 'layer_optimal_facilities',
        pane: 'pane_optimal_facilities',
        filter: locationFilter,
        onEachFeature: pop_optimal_facilities,
        pointToLayer: function (feature, latlng) {
            var context = {
                feature: feature,
                variables: {}
            };
			var blueIcon = new L.Icon(
			   {
                 iconUrl: 'markers/blueplus-1.png',
                 iconSize: [10, 10] 
			   }
		    );
            return new L.Marker(latlng, {icon: blueIcon});
        },
    });
   return layer
}
layer_optimal_facilities = add_layer_optimal_facilities()
map.addLayer(layer_optimal_facilities)
group_optimal_facilities = L.layerGroup([layer_optimal_facilities]).addTo(map);
mapLayerControl.addOverlay(group_optimal_facilities, "{{ _("Optimal Facilities") }}");


/******
 * Baseline facilities
******/
function pop_baseline_facilities(feature, layer) {
    layer.on({
        mouseclick: highlightFeature,
    });
    var popupContent = '<table>\
            <tr>\
            <td>{{ _("Baseline Health Facility") }}<td>\
            </tr>\
            <tr>\
                <th scope="row">adm2</th>\
                <td>' + (feature.properties[adm2_col] !== null ? autolinker.link(feature.properties[adm2_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">adm3</th>\
                <td>' + (feature.properties[adm3_col] !== null ? autolinker.link(feature.properties[adm3_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">lon</th>\
                <td>' + (feature.properties[lon_col] !== null ? autolinker.link(feature.properties[lon_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">lat</th>\
                <td>' + (feature.properties[lat_col] !== null ? autolinker.link(feature.properties[lat_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <th scope="row">plus</th>\
                <td><a href="http://www.google.com/maps/place/' + (feature.properties[plus_col] !== null ? autolinker.link(feature.properties[plus_col].toLocaleString().replace('+', '%2B')) : '') + '" target="_blank">' + (feature.properties[plus_col] !== null ? autolinker.link(feature.properties[plus_col].toLocaleString()) : '') + '</a></td>\
            </tr>\
            ' + (feature.properties[info_col] !== null ? autolinker.link(feature.properties[info_col].toLocaleString()) : '') + '</td>\
        </table>';
    layer.bindPopup(popupContent, {maxHeight: 400});
}


map.createPane('pane_baseline_facilities');
map.getPane('pane_baseline_facilities').style.zIndex = 402;
map.getPane('pane_baseline_facilities').style['mix-blend-mode'] = 'normal';

function add_layer_baseline_facilities(){
    var layer = new L.geoJson(baseline_facilities, {
        attribution: '',
        interactive: true,
        dataVar: 'json_baseline_facilities',
        layerName: 'layer_baseline_facilities',
        pane: 'pane_baseline_facilities',
        filter: locationFilter2,
        onEachFeature: pop_baseline_facilities,
        pointToLayer: function (feature, latlng) {
            var context = {
                feature: feature,
                variables: {}
            };
			var redIcon = new L.Icon(
			   {
                 iconUrl: 'markers/redplus-1.png',
                 iconSize: [10, 10] 
			   }
		    );
            return new L.Marker(latlng, {icon: redIcon});
        },
    });
   return layer
}
if (has_baseline) {
    layer_baseline_facilities = add_layer_baseline_facilities()
    map.addLayer(layer_baseline_facilities)
    group_baseline_facilities = L.layerGroup([layer_baseline_facilities]).addTo(map);
    mapLayerControl.addOverlay(group_baseline_facilities, "{{ _("Baseline Facilities") }}");
}

/******
 * Village centers
 ******/

function pop_village_centers(feature, layer) {
    layer.on({
        mouseclick: highlightFeature,
        });
        var popupContent = '<table>\
                <tr>\
                    <td>{{ _("Village Center") }}</td>\
                </tr>\
                <tr>\
                <th scope="row">adm2</th>\
                    <td>' + (feature.properties[adm2_col] !== null ? autolinker.link(feature.properties[adm2_col].toLocaleString()) : '') + '</td>\
                </tr>\
                <tr>\
                <th scope="row">adm3</th>\
                    <td>' + (feature.properties[adm3_col] !== null ? autolinker.link(feature.properties[adm3_col].toLocaleString()) : '') + '</td>\
                </tr>\
                <tr>\
                <th scope="row">adm4</th>\
                    <td>' + (feature.properties[adm4_col] !== null ? autolinker.link(feature.properties[adm4_col].toLocaleString()) : '') + '</td>\
                </tr>\
                <tr>\
                <th scope="row">lon</th>\
                    <td>' + (feature.properties[lon_col] !== null ? autolinker.link(feature.properties[lon_col].toLocaleString()) : '') + '</td>\
                </tr>\
                <tr>\
                <th scope="row">lat</th>\
                    <td>' + (feature.properties[lat_col] !== null ? autolinker.link(feature.properties[lat_col].toLocaleString()) : '') + '</td>\
                </tr>\
            </table>';
    layer.bindPopup(popupContent, popupOptions, {maxHeight: 400});
}

function style_village_centers() {
    return {
        pane: 'pane_village_centers',
        radius: 6,
        stroke: false,
        fill: true,
        fillOpacity: 1,
        fillColor: 'rgba(51,210,8,1.0)',
        interactive: true,
    }
}
map.createPane('pane_village_centers');
map.getPane('pane_village_centers').style.zIndex = 403;
map.getPane('pane_village_centers').style['mix-blend-mode'] = 'normal';

function add_layer_village_centers(){
    var layer = new L.geoJson(village_centers, {
        attribution: '',
        interactive: true,
        dataVar: 'json_village_centers',
        layerName: 'layer_village_centers',
        pane: 'pane_village_centers',
        filter: locationFilter2,
        onEachFeature: pop_village_centers,
        pointToLayer: function (feature, latlng) {
            var context = {
                feature: feature,
                variables: {}
            };
            return L.shapeMarker(latlng, style_village_centers(feature));
        },
    });
    return layer
}
layer_village_centers = add_layer_village_centers()
// bounds_group.addLayer(layer_village_centers);
map.addLayer(layer_village_centers);
group_village_center = L.layerGroup([layer_village_centers]).addTo(map);
mapLayerControl.addOverlay(group_village_center, "{{ _("Village Centers") }}");

/******
 * GADM
 ******/
function pop_gadm(feature, layer) {
    layer.on({
        mouseclick: highlightFeature,
    });
    var popupContent = '<table>\
            <tr>\
                <td colspan="2">' + (feature.properties[gadm_adm0_col] !== null ? autolinker.link(feature.properties[gadm_adm0_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[gadm_adm1_col] !== null ? autolinker.link(feature.properties[gadm_adm1_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[gadm_adm2_col] !== null ? autolinker.link(feature.properties[gadm_adm2_col].toLocaleString()) : '') + '</td>\
            </tr>\
             <tr>\
                <td colspan="2">' + (feature.properties[gadm_adm3_col] !== null ? autolinker.link(feature.properties[gadm_adm3_col].toLocaleString()) : '') + '</td>\
            </tr>\
        </table>';
    layer.bindPopup(popupContent, {maxHeight: 400});
}

function style_gadm_0() {
    return {
        pane: 'pane_gadm',
        interactive: false,
    }
}
function style_gadm_1() {
    return {
        pane: 'pane_gadm',
        opacity: 0.1,
        color: 'rgba(FF,00,EF,0.1)',
        dashArray: '',
        lineCap: 'round',
        lineJoin: 'round',
        weight: 0.5,
        fillOpacity: 0.1,
        interactive: false,
    }
}
map.createPane('pane_gadm');
map.getPane('pane_gadm').style.zIndex = 400;
map.getPane('pane_gadm').style['mix-blend-mode'] = 'difference';
var layer_gadm = new L.geoJson.multiStyle(gadm, {
    attribution: '',
    interactive: false,
    dataVar: 'json_gadm',
    layerName: 'layer_gadm',
    pane: 'pane_gadm',
    onEachFeature: pop_gadm,
    styles: [style_gadm_0,style_gadm_1,]
});
bounds_group.addLayer(layer_gadm);
map.addLayer(layer_gadm);
function pop_clustered_households(feature, layer) {
    layer.on({
        mouseout: function(e) {
            if (typeof layer.closePopup == 'function') {
                layer.closePopup();
            } else {
                layer.eachLayer(function(feature){
                    feature.closePopup()
                });
            }
        },
        mouseover: highlightFeature,
    });
    var popupContent = '<table>\
            <tr>\
                <td>{{ _("Household") }}</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[adm2_col] !== null ? autolinker.link(feature.properties[adm2_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[adm3_col] !== null ? autolinker.link(feature.properties[adm3_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[lon_col] !== null ? autolinker.link(feature.properties[lon_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[lat_col] !== null ? autolinker.link(feature.properties[lat_col].toLocaleString()) : '') + '</td>\
            </tr>\
            <tr>\
                <td colspan="2">' + (feature.properties[cluster_col] !== null ? autolinker.link(feature.properties[cluster_col].toLocaleString()) : '') + '</td>\
            </tr>\
        </table>';
    layer.bindPopup(popupContent, {maxHeight: 400});
}

/***************************************************
 * allow drag and drop with custom long and lat name
 ***************************************************/
var custom_geolayer = null;
var toggleButton = document.getElementById('toggleLayerBtn');
map.createPane('myCustomPane');
map.getPane('myCustomPane').style.zIndex = 410;

toggleButton.onclick = function() {
    if (custom_geolayer !== null) {
        map.removeLayer(custom_geolayer); // Remove the custom layer from the map
        custom_geolayer = null;
        toggleButton.style.display = 'none'; // Hide the button again
    }
};

function dragOverHandler(ev) {
    console.log('File(s) in drop zone');

    // Prevent default behavior (Prevent file from being opened)
    ev.preventDefault();
}

function dropHandler(ev) {
    console.log('File(s) dropped');
    // Prevent default behavior (Prevent file from being opened)
    ev.preventDefault();

    if (ev.dataTransfer.items) {
        // Use DataTransferItemList interface to access the file(s)
        for (var i = 0; i < ev.dataTransfer.items.length; i++) {
            // If dropped items aren't files, reject them
            if (ev.dataTransfer.items[i].kind === 'file') {

                 // Prompt for column names after file drop
                var lon_col_name = prompt("Enter longitude column name:");
                var lat_col_name = prompt("Enter latitude column name:");
                var custom_title = prompt("Enter name for display your custom data:");

                var file = ev.dataTransfer.items[i].getAsFile();
                var reader = new FileReader();
                reader.onload = function() {
                    if (reader.readyState != 2 || reader.error){
                        return;
                    } else {
                        if(lon_col_name && lat_col_name) {
                            convertToLayer(reader.result, lon_col_name, lat_col_name, custom_title)
                        }

                    }
                };

                reader.addEventListener('progress', (event) => {
                    if (event.loaded && event.total) {
                        const percent = (event.loaded / event.total) * 100;
                        console.log(`Progress: ${Math.round(percent)}`);
                    }
                });
                reader.readAsText(file)
            }
        }
    }
}

function convertToLayer(CSV, lon, lat, custom_title) {
    var lon_c = lon
    var lat_c = lat
    var title_c = custom_title
    toggleButton.click();
    custom_geolayer = L.geoCsv(CSV, {
        longitudeTitle: lon_c,
        latitudeTitle: lat_c,
        firstLineTitles: true,
        fieldSeparator: ',',
        pointToLayer: function (feature, latlng) {
            var marker = L.circleMarker(latlng, {
                radius: 8,
                fillColor: '#969696',
                fillOpacity: 0.8,
                color: '#252525',
                weight: 1,
                });
            // Bind a tooltip to the custom marker with custom title
            // marker.bindTooltip(title_c + ":<br>Longitude: " + feature.geometry.coordinates[0] + "<br>Latitude: " + feature.geometry.coordinates[1]);
            return marker
        },
        onEachFeature: function(feature, layer) {
            layer.on({
                mouseclick: highlightFeature,
            });
            layer.bindPopup(title_c + ":<br>Longitude: " + feature.geometry.coordinates[0] + "<br>Latitude: " + feature.geometry.coordinates[1], {maxHeight: 400})
        }
    });
    custom_geolayer.addTo(map);
    custom_geolayer.options.pane = 'myCustomPane';
    toggleButton.style.display = 'block'; // Make the button visible
}
