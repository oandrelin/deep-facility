import shutil

from deepfacility.config.config import Config
from deepfacility.flows import DataPrepWorkflow, ScientificWorkflow
from deepfacility.utils import util


def cmd_prep(cfg: Config) -> None:
    adm_files, hh_file, vc_file, bl_file, ok = DataPrepWorkflow(cfg=cfg).prepare_inputs(cfg.args.country)
    if ok:
        cfg.inputs.logger.info("Prepared input files:")
        cfg.inputs.logger.info("\n".join([str(f) for f in adm_files] + [str(hh_file), str(vc_file), str(bl_file)]))


def cmd_run(cfg: Config, cli: bool = True) -> bool:
    """Run the scientific workflow."""
    # Cleanup previous run
    shutil.rmtree(cfg.results.dir, ignore_errors=True)
    
    # Get the locations string
    locations_txt = get_locations_str(cfg)
    if not locations_txt:
        return False

    if cli:
        # Log the command arguments
        log_command_args(cfg, "run", locations_txt)
    
    # Save the locations file
    util.make_dir(cfg.results.locations_file)
    cfg.results.locations_file.write_text(locations_txt)
    
    # Run the workflow
    rs, failed = ScientificWorkflow(cfg=cfg).process_locations()
    
    # Log the results
    if rs:
        cfg.results.logger.info("Merged files:")
        cfg.results.logger.info(f"  village shapes:     {rs.shape_file}")
        cfg.results.logger.info(f"  cluster households: {rs.clusters_file}")
        cfg.results.logger.info(f"  facility placement:  {rs.facilities_file}")
    else:
        cfg.results.logger.info("No results found.")

    if failed:
        cfg.results.logger.info()
        cfg.results.logger.info("Failed locations:")
        for ff in failed:
            cfg.results.logger.info(f"  {ff}")

    # logger.handlers.clear()

    return True


def get_locations_str(cfg: Config) -> str:
    """Get locations string for logging."""
    # Prepare the string containing the list of locations
    if cfg.has_locations:
        locations_txt = "\n".join(cfg.locations)
    else:
        locations_txt = ""
        loc = f" for filter(s) {','.join(cfg.locations)}" if cfg.locations else ""
        cfg.inputs.logger.warning(f"No locations found: {loc}")
    
    return locations_txt


def log_command_args(cfg: Config, command: str,
                     locations_txt, 
                     show_locations: bool = False) -> None:
    """Log the command arguments."""
    logger = cfg.results.logger
    # Log the command and its arguments
    logger.info("---")
    logger.info(f"Command:     {command}")
    logger.info("Options:")
    logger.info(f"  run:       {cfg.run_name}")
    logger.info(f"  config:    {cfg.config_file}")
    logger.info(f"  results:   {str(cfg.results.locations_file.parent)}")
    logger.info(f"  locations: {' '.join(cfg.location_filter) or 'all'}")
    if show_locations or cfg.location_filter:
        logger.info(f"---\n{locations_txt}")
    if locations_txt:
        logger.info("---")
