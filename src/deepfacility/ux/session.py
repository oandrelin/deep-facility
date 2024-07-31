import os
import shutil

import time
import tomli
import tomli_w

from pathlib import Path
from fastapi import Request, BackgroundTasks
from dataclasses import dataclass

from deepfacility import lang
from deepfacility.config.config import Config, Inputs, Operation, Results, create_config_file, read_s2_dict
from deepfacility.utils import util

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

# initiate app here to use app.state to preserve session
app = FastAPI()

# initiate templates here to set `_` translation function in the session init
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@dataclass
class ConfigForm:
    """Config file form data."""
    # Country
    country: str
    country_code: str
    # Village centers
    village_file: str
    village_name_col: str
    village_lon_col: str
    village_lat_col: str
    # Baseline facilities
    baseline_file: str = ""
    baseline_lon_col: str = ""
    baseline_lat_col: str = ""
    baseline_info_cols: list[str] = None


@dataclass
class Session:
    """Session data."""
    session_id: str = None
    session_dir: Path = None
    village_file: Path = ""
    baseline_file: Path = ""
    cfg: Config = None
    start_time: float = time.time()
    translator: lang.Translator = None
    _operation: Operation = None
    
    @property
    def data_dir(self):
        """Get the directory containing country files."""
        return self.session_dir / "data"

    @classmethod
    def get_session_id(cls, request: Request) -> str:
        """Get the session id from one of the possible sources"""
        session_id = os.environ.get('DEEPFACILITY_SID', None)         # from env variable
        session_id = session_id or request.query_params.get("sid")    # from query string
        session_id = session_id or request.cookies.get("session_id")  # from cookie
        session_id = session_id or util.new_session_id(length=12)     # generate a new one
        return session_id

    
    @classmethod
    def get_session_dir(cls, session_id: str) -> Path:
        """Get the session directory."""
        return util.app_dir() / session_id
        
    @classmethod
    def init(cls, request: Request, language: str = ""):
        """Initialize the session."""
        global app
        assert isinstance(app, FastAPI), "FastAPI app is not initialized"
                
        has_s_dict = app and hasattr(app.state, 'session') and isinstance(app.state.session, dict)
        if not has_s_dict:
            app.state.session = {}

        # Get session id
        session_id = cls.get_session_id(request)

        s: Session = app.state.session.get(session_id, None)
        
        if s:
            s.session_id = session_id
            
            # For existing session
            if s.translator is None:
                # Create a new translator if not set
                s.translator = lang.Translator.create(language, request)
            elif language:
                # Set the language if different
                if s.translator.language != language:
                    s.translator.set_language(language)
            else:
                pass
        else:
            # For a new session
            config_file = None
            for file in Session.get_session_dir(session_id).glob("*.toml"):
                if not config_file or file.stat().st_ctime > config_file.stat().st_ctime:
                    # Take the latest config toml file
                    config_file = file
                
            # Create a config instance (using the latest config file, if exists)
            cfg = Config.create_instance(config_file=config_file) if config_file else None
            
            # Create a session and set the translator
            s = Session(cfg=cfg, session_id=session_id, translator=lang.Translator.create(language, request))
            
            # Set the session directory
            s.session_dir = cls.get_session_dir(session_id)
            
            app.state.session[s.session_id] = s
        
        # Set the translator in the global Jinja2 environment
        templates.env.globals['_'] = s.translator.translate

        return s

    def init_cfg(self, cf: ConfigForm):
        """Initialize the config from the config form."""
        # Create the config file
        stem: str = Path(cf.village_file).stem
        config_file = self.session_dir / Path(Config.default_file).with_suffix(f".{stem}.toml").name
        create_config_file(config_file, force=True)
        
        # Read default config from the file
        content = config_file.read_text()
        cfg_dict = tomli.loads(content)
        
        # Get the country code
        country_code: str = str(read_s2_dict()[cf.country]["code"])
        
        # Get the village file pattenr and populate it
        ptt = cfg_dict['args']['village_centers']['file']
        cfg_data_dir = str(self.data_dir) 
        ptt = ptt.replace("{data_dir}", cfg_data_dir)
        ptt = ptt.replace("{country_code}", country_code)
        args_dir = Path(ptt).parent

        def to_args_dir(file: str) -> str:
            """Move uploaded files from tempt to args dir"""
            file2 = args_dir / Path(file).name
            file2.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(file, file2)
            return str(file2)

        # Move the village file
        cf.village_file = to_args_dir(cf.village_file)
        
        # Update config with values from the form
        cfg_dict['args']['data_dir'] = cfg_data_dir
        cfg_dict['args']['country'] = cf.country
        cfg_dict['args']['country_code'] = country_code
        
        cfg_dict['args']['village_centers']['file'] = cf.village_file
        cfg_dict['args']['village_centers']['adm_cols'] = [cf.village_name_col]
        cfg_dict['args']['village_centers']['xy_cols'] = [cf.village_lon_col, cf.village_lat_col]

        if Path(cf.baseline_file).is_file():
            cf.baseline_file = to_args_dir(cf.baseline_file)
            cfg_dict['args']['baseline_facilities']['file'] = cf.baseline_file
            cfg_dict['args']['baseline_facilities']['xy_cols'] = [cf.baseline_lon_col, cf.baseline_lat_col]
            cfg_dict['args']['baseline_facilities']['info_cols'] = cf.baseline_info_cols
        else:
            cfg_dict['args']['baseline_facilities']['file'] = ""
        
        # Write the updated config to the file
        content = tomli_w.dumps(cfg_dict)
        config_file.write_text(content)
        
        # Create a new config instance
        self.cfg: Config = Config.create_instance(config_file=config_file)

    def get_config_form(self):
        """Get the config form for the current config file."""
        # Prepare response dict containing key confing info to be displayed in the driver
        return ConfigForm(country=self.cfg.args.country,
                          country_code=self.cfg.args.country_code,
                          # village centers
                          village_file=self.cfg.args.village_centers.file.name,
                          village_name_col=self.cfg.args.village_centers.adm_cols[-1],
                          village_lon_col=self.cfg.args.village_centers.xy_cols[0],
                          village_lat_col=self.cfg.args.village_centers.xy_cols[1],
                          # baseline facilities
                          baseline_file=self.cfg.args.baseline_facilities.file.name,
                          baseline_lon_col=self.cfg.args.baseline_facilities.xy_cols[0],
                          baseline_lat_col=self.cfg.args.baseline_facilities.xy_cols[1],
                          baseline_info_cols=self.cfg.args.baseline_facilities.info_cols)

    @property
    def has_task(self) -> bool:
        """Check if there is a running task."""
        return self._operation is not None
        
    @property
    def has_prep_task(self) -> bool:
        """Check if there is a running data prep task."""
        return self._operation is not None and isinstance(self._operation, Inputs)
    
    @property
    def has_run_task(self) -> bool:
        """Check if there is a running scientific workflow task."""
        return self._operation is not None and isinstance(self._operation, Results)

    def start_task(self, op: Operation, background_tasks: BackgroundTasks, task_fn: callable, *args, **kwargs):
        """
        Start a background task.
        :param op: Operation instance
        :param background_tasks: FastAPI background tasks
        :param task_fn: Task function to run
        """
        # Clear the previous task if it exists
        if self._operation and self._operation.is_stopped():
            time.sleep(5)
            self._operation.clear()
            self._operation = None
        
        # Start the new task
        background_tasks.add_task(task_fn, *args, **kwargs)
        self._operation = op
    
    def clear_task(self):
        """Clear the current task."""
        if self._operation:
            self._operation = None
    
    def stop_task(self):
        """Create the stop file to signal the background task to stop."""
        if self._operation:
            self._operation.stop()
            self.clear_task()
        # else:
        #     self._operation.logger.warning("No task to stop")
        
    def has_config_file(self):
        """Check if the session has a config file."""
        return self.cfg and self.cfg.config_file and self.cfg.config_file.is_file()


def is_localhost(request):
    """Check if the request is from localhost."""
    hosts = ["localhost", "127.0.0.1", "0.0.0.0"]
    return any([request.headers.get("host").startswith(v) for v in hosts])
