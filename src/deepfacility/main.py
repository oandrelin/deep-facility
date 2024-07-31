import argparse
import os

import time
import sys
import shutil

from pathlib import Path

from deepfacility.utils import commands, util
from deepfacility.viz import visualize

from deepfacility.config.config import RuntimeArgs, Config, get_supported_countries, create_config_file


def parse_args() -> argparse.Namespace:
    example = "deepfacility run"
    parser = argparse.ArgumentParser(example)
    # Commands
    available_commands = ['countries', 'config', 'prep', 'locations', 'run', 'viewmap', 'ux', 'reset']
    parser.add_argument('command', choices=available_commands, help="Command to execute.")
    # Optional arguments
    parser.add_argument('-l', '--locations', dest='location_filter', nargs='+', default=[],
                        help="Location string or file path. If not provided, all locations are used.")
    parser.add_argument('-c', '--config', dest='config_file', default=Config.default_file,
                        help="Config file path.")
    parser.add_argument('-n', '--name', dest='run_name', default='',
                        help="Run name, used as a output dir suffix.")
    parser.add_argument('-r', '--resultdir', dest='result_dir', default='', required='viewmap' in sys.argv,
                        help="Target dir where the results map files are stored.")
    parser.add_argument('--sid', dest='session_id', default='',
                        help="Web app session ID to be used in a single-user scenario.")
    args = parser.parse_args()

    return args


def main():
    ts0 = time.time()
    args_raw: argparse.Namespace = parse_args()
    runtime_args = {k: v for k, v in args_raw.__dict__.items() if k in RuntimeArgs().__dict__}
    args: RuntimeArgs = RuntimeArgs(**runtime_args)
    if args.command == "reset":
        # Remove memory cache dir
        shutil.rmtree(util.memory_cache_dir(), ignore_errors=True)
        exit(0)
        
    elif args.command == "ux":
        # Start demo web app
        os.environ['DEEPFACILITY_ROOT_DIR'] = str(util.app_dir())
        if args_raw.session_id:
            os.environ['DEEPFACILITY_SID'] = args_raw.session_id
        os.chdir(Path(__file__).parent.joinpath('ux'))
        import deepfacility.ux.main as ux_main
        ux_main.main()
        exit(0)

    elif args.command == "config":
        # Create a config file from the user template file
        create_config_file(args.config_file)
        exit(0)
    
    # Create a config instance based on input arguments
    cfg: Config = Config.create_instance(run_args=args)
    
    match args.command:
        case "prep":
            # Run the data preparation command.
            commands.cmd_prep(cfg)
        case "countries":
            # List supported countries, which can be set in the config file.
            cfg.inputs.logger.info("Supported countries (you can set in config):")
            cfg.inputs.logger.info('\n'.join(get_supported_countries()))
            
        case "viewmap":
            # Create an interactive visualization map from the results.
            cfg.results.logger.info("Creating leaflet map:")
            visualize.Visualizer(cfg=cfg).create_leaflet_map(result_dir=Path(args.result_dir))
            
        case "locations":
            # List locations, which can be used in the scientific workflow.
            locations_str = commands.get_locations_str(cfg)
            if locations_str:
                commands.log_command_args(cfg, command='locations', locations_txt=locations_str, show_locations=True)
            else:
                cfg.results.logger.warning("Make sure to prepare input files using the 'prep' command.")
            exit(0)
            
        case "run":
            if not cfg.has_locations:
                cfg.results.logger.warning("No locations found.")
                exit(0)

            # Run the scientific workflow.
            done = commands.cmd_run(cfg)
            if not done:
                exit(0)
        case _:
            raise ValueError("Unsupported command.")

    cfg.results.logger.info(f"Finished processing in: {util.elapsed_time_str(ts0)}")
    exit(0)


if __name__ == "__main__":
    main()
