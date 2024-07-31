import shutil
import time

import fastapi
import warnings

import importlib.metadata
import pandas as pd
import uvicorn

from dataclasses import asdict
from fastapi import File, UploadFile, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from tempfile import mkdtemp

from deepfacility.flows import DataPrepWorkflow
from deepfacility.lang import Translator
from deepfacility.utils import commands, spatial, util
from deepfacility.viz import visualize

from deepfacility.config.config import Config, AdmPointsFile, BaselineFile, get_all_locations
from deepfacility.ux.session import Session, ConfigForm, is_localhost, app, templates

warnings.simplefilter(action='ignore', category=FutureWarning)


# app and  templates are initiated in the session module
app.mount("/css", StaticFiles(directory=str(Path(__file__).parent / "css")), name="css")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, language: str = Form(default="")):
    """The main page of the application."""
    # Initialize session
    s = Session.init(request, language=language)

    # Get supported languages for the language selector
    all_languages = s.translator.supported_languages
    context = {"request": request,
               "version": importlib.metadata.version('deepfacility'),
               "language": s.translator.language,
               "session_id": s.session_id,
               "all_languages": all_languages}

    # Render the index app page
    response = templates.TemplateResponse("index.html", context)
    # Set the session cookie to last 10 years
    response.set_cookie("session_id", s.session_id, max_age=315360000, httponly=True)
    return response


@app.post("/lang", response_class=HTMLResponse)
def select_language(request: Request, language: str = Form(...)):
    """Set session language, then redirect to index."""
    Session.init(request, language=language)
    # Redirect to the index page to refresh UI content
    # HTTP_302_FOUND is necessary to allow the browser to redirect
    return RedirectResponse('/', status_code=fastapi.status.HTTP_302_FOUND)


@app.get("/driver", response_class=HTMLResponse)
def driver(request: Request):
    """The main driver page showing clustering UI when app is configured."""
    s = Session.init(request)

    # Check if app is configured and inputs are redy
    if s.has_config_file() and s.cfg.inputs.ready():
        # Get the list of existing runs
        root_dir = s.cfg.results.root_dir
        result_dirs = list(root_dir.glob("*"))
        result_names = []
        if result_dirs and len(result_dirs) > 0:
            # Filter complete runs
            result_dirs = sorted(
                [(d.lstat().st_mtime, d.stem, d.joinpath("locations.csv").read_text())
                 for d in result_dirs
                 if d.is_dir()
                    and d.joinpath("optimal_facilities.csv").is_file()
                    and d.joinpath("locations.csv").is_file()
                 ], reverse=True)
    
            # Put the latest on top and sort rest by name
            if len(result_dirs) > 0:
                result_dirs = [result_dirs[0]] + sorted(result_dirs[1:], key=lambda x: x[1])
                result_names = [(d, locs) for _, d, locs in result_dirs]
                
        context = {
            "request": request,
            "locations": get_all_locations(s.cfg),
            "result_names": result_names,
            "show_large": "false"
            }
        
        response = templates.TemplateResponse("40-run.html", context)
    else:
        # app is not configured or inputs are not ready
        response = ''
        
    return response


@app.get("/clear_view", response_class=HTMLResponse)
def clear_view(request: Request):
    """Clear the map view element."""
    s = Session.init(request)
    
    if s.has_prep_task:
        status_page = "30-prep-status-container.html"
    elif s.has_run_task:
        status_page = "40-run-status-container.html"
    else:
        status_page = None

    context = {"request": request}
    if status_page:
        # Navigate to the page which sends regular status requests and displays the status
        response = templates.TemplateResponse(status_page, context)
    else:
        # Return an empty `view` div to clear the map view element.
        response = HTMLResponse(content=get_empty_div("view"), status_code=200)

    return response


@app.get("/new", response_class=HTMLResponse)
def new_config(request: Request):
    """Display Yes/No buttons for the New Config button."""
    # Initialize session to ensure language is set
    Session.init(request)
    # Pressing `Yes` button sends `oknew` request, otherwise `/info`.
    context = {"request": request}
    return templates.TemplateResponse("12-confirm-new.html", context)


@app.get("/oknew", response_class=HTMLResponse)
def ok_new_config(request: Request):
    """Deletes the config, stops background tasks, redirects to `upload`."""
    s = Session.init(request)
    s.stop_task()
    if s.has_config_file():
        s.cfg.config_file.unlink(missing_ok=True)

    context = {"request": request}
    response = templates.TemplateResponse("10-upload.html", context)
    return response


@app.get("/info", response_class=HTMLResponse)
def info(request: Request):
    """
    Display the config info at the top if configured.
    Otherwise, navigate to the upload form to allow user to configure.
    """
    s = Session.init(request)

    # Check if app is configured and inputs are ready
    if s.has_config_file() and s.cfg.inputs.ready():
        # If ready show the config info at the top
        # Prepare response dict containing key confing info
        cf_dict = asdict(s.get_config_form())
        # Detect if app is running locally
        if is_localhost(request):
            # Add app dir path to the config info to display in UI
            # to help users manually access the dir
            cf_dict['local_path'] = str(s.cfg.results.root_dir)
        else:
            # If not running locally, don't show the app path
            cf_dict['local_path'] = ""
            
        context = {"request": request, "session_id": s.session_id, **cf_dict}
        response = templates.TemplateResponse("22-info.html", context)
    elif s.has_config_file():
        df, df_b = get_preview_dfs(s.cfg)
        
        context = {"request": request,
                   "village_preview": df.head().to_html(index=False),
                   "baseline_preview": df_b.head().to_html(index=False) if df_b is not None else "",
                   **asdict(s.get_config_form())
                   }
        response = templates.TemplateResponse("30-prep.html", context)
    
    elif not s.has_config_file() :
        # If not ready navigate to the upload page
        context = {"request": request}
        response = templates.TemplateResponse("10-upload.html", context)
    else:
        response = ""
        
    return response


@app.post("/upload", response_class=HTMLResponse)
def upload_csv(request: Request,
               village_file: UploadFile = File(...),
               baseline_file: UploadFile = File(default="")):
    """Upload the village and baseline files and navigate to the configure page."""
    s = Session.init(request)
    # Read the uploaded file with pandas
    try:
        # Init session village file
        tmp_dir = Path(mkdtemp())
        s.village_file = tmp_dir / village_file.filename
        
        # Load file, get columns and save to session dir
        df = pd.read_csv(village_file.file, encoding='utf-8')
        village_cols = sorted(df.columns)
        df.to_csv(s.village_file, index=False, encoding='utf-8')
        
        # Check if baseline file is uploaded
        if baseline_file:
            # Load the baseline file
            s.baseline_file = tmp_dir / baseline_file.filename
            df2 = pd.read_csv(baseline_file.file, encoding='utf-8')
            
            def clean(col):
                chrs = [c if c.isalnum() else ' ' for c in col]
                return ''.join(chrs)

            # Remove special characters from column names
            clean_cols = [clean(col) for col in df2.columns]
            
            # Rename columns with clean names and save to the session dir
            df3 = util.rename_df_cols(df2, list(df2.columns), clean_cols)
            baseline_cols = sorted([c for c in clean_cols if not str(c).startswith("Unnamed:")])
            df3.to_csv(s.baseline_file, index=False, encoding='utf-8')
        else:
            # Leave baseline vars empty if file is not uploaded
            s.baseline_file = ""
            baseline_cols = []

    except Exception as e:
        return HTMLResponse(content=f"Error reading file: {e}", status_code=400)
    
    # Prepare dict to display village and baseline files in the config page
    context = {"request": request,
               "village_file": s.village_file.name,
               "village_cols": village_cols,
               "baseline_file": s.baseline_file.name if baseline_file else "",
               "baseline_cols": baseline_cols}
    
    return templates.TemplateResponse("20-configure.html", context)


@app.post("/config", response_class=HTMLResponse)
def configure(request: Request,
              village_name_col: str = Form(...),
              village_lon_col: str = Form(...),
              village_lat_col: str = Form(...),
              baseline_lon_col: str = Form(default=""),
              baseline_lat_col: str = Form(default=""),
              baseline_info_cols: list[str] = Form(default="")):
    """Configure the app with based on uploaded village and baseline files."""
    s = Session.init(request)
    
    # Read uploaded village file
    df = pd.read_csv(s.village_file, encoding='utf-8')
    df = df[[village_lon_col, village_lat_col]]
    
    # Detect the country from village centers
    country, code = spatial.detect_country(df=df, xy_cols=[village_lon_col, village_lat_col])

    # Prepare response dict containing key confing info to be displayed in the driver
    cf = ConfigForm(country=country,
                    country_code=code,
                    village_file=str(s.village_file),
                    village_name_col=village_name_col,
                    village_lon_col=village_lon_col,
                    village_lat_col=village_lat_col,
                    baseline_file=str(s.baseline_file),
                    baseline_lon_col=baseline_lon_col,
                    baseline_lat_col=baseline_lat_col,
                    baseline_info_cols=baseline_info_cols)

    # create config
    s.init_cfg(cf)
    cf.village_file = Path(cf.village_file).name
    cf.baseline_file = Path(cf.baseline_file).name

    df, df_b = get_preview_dfs(s.cfg)
    
    context = {"request": request,
               "has_data": s.cfg.inputs.ready(),
               "village_preview": df.head().to_html(index=False),
               "baseline_preview": df_b.head().to_html(index=False) if df_b is not None else "",
               **asdict(cf)}
    
    return templates.TemplateResponse("30-prep.html", context)


@app.get("/prep", response_class=HTMLResponse)
def prep(request: Request, bt: BackgroundTasks):
    """Run data preparation workflow for the detected country."""
    s = Session.init(request)
    
    # Cleanup previous tasks and data
    s.stop_task()  # Stop any running background task
    s.cfg.inputs.remove_files()  # Remove input files
    # Remove all country results
    shutil.rmtree(s.cfg.results.root_dir, ignore_errors=True)
    
    # Start the data preparation task
    s.start_time = time.time()  # capture new start time
    s.start_task(s.cfg.inputs, bt, prep_data, s.cfg, s.translator, s.clear_task)
    
    context = {"request": request}
    
    # Navigate to the page which sends regular status requests and displays the status.
    response = templates.TemplateResponse("30-prep-status-container.html", context)
    
    return response


@app.get("/prep/status/container", response_class=HTMLResponse)
def prep_status_container(request: Request):
    """Data preparation workflow status tracking page."""
    context = {"request": request}
    # The template renders the page which periodically sends
    # `/prep/status` requests and displays responses in the `status` div.
    return templates.TemplateResponse("40-prep-status-container.html", context)


@app.get("/prep/status", response_class=HTMLResponse)
def prep_status(request: Request):
    """Data preparation workflow status page."""
    s = Session.init(request)
    
    # Check if app is not configured or the data preparation task is stopped
    if not s.cfg or s.cfg.inputs.is_stopped():
        # Redirect to driver which will clean up and redirect to upload.
        time.sleep(5)
        return RedirectResponse(url='/driver')
    
    # Alias for the Inputs configuration section
    ins = s.cfg.inputs
    
    # Check if all shape files are present
    shp_x, bld_x, hhs_x, vil_x = (all([f.is_file() for f in ins.shape_files]),
                                  ins.buildings.file.is_file(),
                                  ins.households.file.is_file(),
                                  ins.village_centers.file.is_file())

    shp = bld = hhs = vil = "Not Started"
    
    # Calculate the progress of each step
    if shp_x:
        # Calculate the size of the shape files
        size = ins.shape_files[-1].lstat().st_size // 1000000
        # Set Done if the buildings file (next step) is present.
        shp = "In Progress" if not bld_x else "Done"
        # Construct the status string.
        shp = f"{shp} ({size}MB)"
    else:
        shp = "In Progress (...)"
        
    if bld_x:
        size = ins.buildings.file.lstat().st_size // 1000000
        bld = "In Progress" if not hhs_x else "Done"
        bld = f"{bld} ({size}MB)"
    else:
        bld = "In Progress (...)"
        
    if hhs_x:
        size = ins.households.file.lstat().st_size // 1000000
        hhs = "In Progress" if not vil_x else "Done"
        hhs = f"{hhs} ({size}MB)"
    else:
        hhs = "In Progress (...)"
        
    if vil_x:
        size = ins.village_centers.file.lstat().st_size // 1000
        vil2_x = ins.village_centers.file.with_suffix(".geojson").is_file()
        vil = "In Progress" if not vil2_x else "Done"
        vil = f"{vil} ({size}kB)"
        vil_time = time.time() - ins.village_centers.file.lstat().st_mtime
    else:
        vil_time = 0
    
    # Check if the data preparation task is complete or stopped
    if s.cfg.inputs.ready() and (vil_time > 10 or s.cfg.inputs.is_stopped()):
        s.clear_task()
        return reload_page_response()

    # If still running get latest logs to display in the UI
    prep_logs = get_logs(s.cfg.inputs.log_file)

    # Prepare status response
    elapsed = get_elapsed_time(s.start_time)
    
    # Construct the status response
    context = {"request": request,
               "shp": shp,
               "bld": bld,
               "hhs": hhs,
               "vil": vil,
               "elapsed": elapsed,
               "logs": prep_logs}
    
    return templates.TemplateResponse("30-prep-status.html", context)


@app.post("/run", response_class=HTMLResponse)
def run(request: Request, bt: BackgroundTasks, locs: list[str] = Form(...)):
    """Run the scientific workflow via FastAPI background tasks."""
    s = Session.init(request)
    s.start_time = time.time()
    assert isinstance(locs, list), "The locations field must be a list."
    
    # Don't run if no locations are selected.
    if not locs:
        return ""
    
    if locs:
        # Set selected locations in the config.
        s.cfg.update_locations(locs)
    else:
        s.cfg.update_locations('')
    
    # Clear previous run and start the new background task
    s.cfg.results.remove_files()
    s.start_task(s.cfg.results, bt, run_locs, s.cfg, s.translator, s.clear_task)
    
    # Navigate to the page which sends regular status requests and displays the status.
    context = {"request": request, "show_large": "false"}
    response = templates.TemplateResponse("40-run-status-container.html", context)
    return response


@app.get("/run/status/container", response_class=HTMLResponse)
def run_status_container(request: Request):
    """Scientific workflow status tracking page."""
    # The template renders the page which periodically sends
    # `/run/status` requests and displays responses in the `status` div.
    context = {"request": request}
    return templates.TemplateResponse("40-run-status-container.html", context)


@app.get("/run/status", response_class=HTMLResponse)
def run_status(request: Request):
    """Scientific workflow status page."""
    s = Session.init(request)
    if not s.cfg or not s.cfg.config_file or not s.cfg.config_file.is_file():
        return "Config not found."
           
    locs_file = s.cfg.results.locations_file
    assert locs_file.parent != "all", f"Run name not set properly {locs_file}."
    
    # If the locations file is not present reset the config.
    if not locs_file.is_file():
        s.cfg.results.logger.warning("The configuration was not successful (no locations file). Redirecting to the upload page.")
        
        # Refresh and let `info` and `driver` sections handle the rest
        return reload_page_response()

    # If the run is stopped, reload the page to display the `run` page.
    if s.cfg.results.is_stopped():
        s.clear_task()
        return reload_page_response()
    
    # Check if each location has a facility file.
    locations = locs_file.read_text().splitlines()
    file_ptt = s.cfg.results.facilities.file
    files = [spatial.location_path(file_ptt, loc) for loc in locations]
    files_ok = [f.is_file() for f in files]
    
    if all(files_ok):
        # It is done, reload page to refresh the results list.
        s.clear_task()
        time.sleep(min(len(files_ok), 10))
        return reload_page_response()

    # Not yet done, display status and logs.
    # Construct status to show number of done locations and those still in progress.
    done_count = sum(files_ok)
    res = [(f"{done_count} locations", True)] if done_count > 0 else []
    res += [(f"{f.parent.parent.name}:{f.parent.name}", False)
            for (f, ok) in zip(files, files_ok) if not ok]
    
    # If still running get latest logs to display in the UI
    res_logs = get_logs(s.cfg.results.log_file)

    # Prepare status response
    elapsed = get_elapsed_time(s.start_time)
   
    # Render the status response
    context = {"request": request, "files": res, "elapsed": elapsed, "res_logs": res_logs}
    return templates.TemplateResponse("40-run-status.html", context)


@app.get("/run/stop", response_class=HTMLResponse)
def stop_run(request: Request):
    """Stop the background tasks."""
    s = Session.init(request)
    s.stop_task()
    # Return a message to display in the UI
    return HTMLResponse(s.translator.translate("Stopping..."))


@app.post("/view", response_class=HTMLResponse)
def show_results(request: Request,
                 result_name: str = Form(...),
                 show_large: str = Form(...)):
    """Display the map with the run results"""
    s = Session.init(request)

    # For running tasks, display status
    if s.has_task:
        context = {"request": request}
        response = templates.TemplateResponse("40-run-status-container.html", context)
        return response
    
    # If no run name clear the `downloads` section
    if result_name == "None" and show_large == "None":
        return "<div id='downloads' />"
    
    run_dir = s.cfg.results.root_dir / result_name
    dirs = [str(d) for d in list(run_dir.glob("*")) if d.is_dir() and d.name != 'www']
    for d in dirs:
        shutil.rmtree(str(d))

    result_files = [str(f.name) for f in get_result_files(run_dir)]

    # Check if the map can be displayed
    if show_large == "false":
        # Tool many location can cause the map to be non-responsive
        # This can be overridden by setting the `show_large` to `true`
        msg = check_max_locations(s.cfg, run_dir.joinpath("locations.csv"))
        if msg:
            return msg

    # Construct the map URL and dir
    result_url = f"/viewmap/{result_name}"
    result_dir = run_dir / 'www'
    
    n = 0
    # Wait for the map to be ready
    while not result_dir.is_dir() and n < 5:
        time.sleep(1)
        n += 1
    
    # If the map is ready, display it
    if result_dir.is_dir():
        # Mount the map directory to the app routes
        app.mount(result_url, StaticFiles(directory=result_dir), name="static")
        context = {'request': request,
                   'result_name': result_name,
                   'result_url': f"{result_url}/index.html",
                   'result_files': result_files}
        return templates.TemplateResponse("50-map.html", context)
    else:
        return "Map is not ready.<div id='downloads' />"


@app.post("/remove", response_class=RedirectResponse)
def remove_results(request: Request, result_name: str = Form(...)):
    """Remove the selected run results."""
    s = Session.init(request)
    run_dir = s.cfg.results.root_dir / result_name
    # failsafe check
    if run_dir.is_dir() and run_dir.parent.samefile(s.cfg.results.root_dir):
        shutil.rmtree(run_dir)
    else:
        s.cfg.results.logger.warning(f"Directory doesn't appear to be a valid 'run' directory: {run_dir}")
    
    # Redirect to the index page to refresh the results list
    # HTTP_302_FOUND is necessary to allow the browser to redirect
    return RedirectResponse('/', status_code=fastapi.status.HTTP_302_FOUND)
    

@app.post("/download", response_class=FileResponse)
def download_results(request: Request, result_name: str = Form(...)):
    """Download the selected run results as a zip file."""
    s = Session.init(request)
    
    # Construct the zip file name and path
    file_name = f"{s.cfg.args.country_code}-{result_name}.zip"
    res_dir = s.cfg.results.root_dir / result_name
    
    # Get result files to be zipped
    res_files = get_result_files(res_dir)
    assert all([result_name in str(f) for f in res_files]), f"{result_name} not present in result file paths."
    path = util.create_zip(res_files, zip_name=file_name)
    
    # Return the zip file as a response, will prompt the user to download
    return FileResponse(path=path, filename=file_name, media_type='application/zip')


# Workflow helpers

def get_preview_dfs(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    # Read uploaded village file
    vc: AdmPointsFile = cfg.args.village_centers
    bs: BaselineFile = cfg.args.baseline_facilities
    
    df0 = pd.read_csv(vc.file, encoding='utf-8')
    df = df0[[vc.adm_cols[-1], *vc.xy_cols]]
    
    if bs.file and bs.file.is_file():
        # Read uploaded baseline file, if available
        df_b0 = pd.read_csv(bs.file, encoding='utf-8')
        df_b0 = df_b0.reset_index()
        df_b = df_b0[['index', *bs.xy_cols, *bs.info_cols]]
    else:
        df_b = None
    
    return df, df_b


# Background tasks functions


def prep_data(cfg: Config, translator: Translator, clean_fn):
    """Background task function for preparing data for the selected country."""
    t = DataPrepWorkflow(cfg=cfg).prepare_inputs(cfg.args.country)
    if t[-1]:
        time.sleep(3)
        cfg.inputs.logger.info("Completed data preparation!")
    else:
        cfg.inputs.logger.warning("Cancelled data preparation.")
    
    clean_fn()
    

def run_locs(cfg: Config, translator: Translator, clean_fn):
    """Background task function for running the scientific workflow."""
    done = commands.cmd_run(cfg=cfg, cli=False)
    if done and not cfg.results.is_stopped() and cfg.results.ready():
        # Create the interactive map for the run results.
        visualize.Visualizer(cfg=cfg).create_leaflet_map(
            result_dir=cfg.results.dir,
            translator=translator)
    clean_fn()


# Helper functions


def check_max_locations(cfg: Config, loc_file: Path):
    """
    Prevent non--responsive map visualization if
    the number of locations is too large.
    """
    if loc_file.is_file():
        loc_count = len(list(loc_file.read_text().split('\n')))
    else:
        loc_count = 0

    max_count = cfg.results.viz_max_locations
    if loc_count == 0:
        msg = "No locations found."
    elif loc_count > max_count:
        msg = f"The number of locations is greater than {max_count}."
    else:
        msg = ""

    return msg


def get_logs(log_file):
    """Get the last 30 lines of the log file."""
    if log_file.is_file():
        logs = log_file.read_text().splitlines()[-30:]
    else:
        logs = ""

    return logs


def get_elapsed_time(start_time):
    """Get the elapsed time since the start of the task."""
    et = util.elapsed_time(start_time)
    elapsed = f"{et['m']}m:{et['s']}s"
    return elapsed


def get_result_files(res_dir: Path) -> list[Path]:
    """Get the list of files in the result directory."""
    files = list(res_dir.glob("*.csv"))
    files += list(res_dir.glob("*.geojson"))
    files += list(res_dir.glob("*.png"))
    files += list(res_dir.glob("*.log"))

    return files


def get_empty_div(id):
    """Return an empty div element with the specified id."""
    return f"<div id='{id}' ></div>"


def reload_page_response(seconds=7):
    """Reload the page after a delay."""
    time.sleep(seconds)
    return HTMLResponse("<script>location.reload()</script>")


def main():
    import os
    host = os.environ.get('DEEPFACILITY_HOST', "localhost")
    port = int(os.environ.get('DEEPFACILITY_PORT', "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
